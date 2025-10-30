import socket
import whois
from logging_.engine_logger import get_engine_logger

log = get_engine_logger()


def check_domain_dns_whois(domain: str) -> dict:
    """
    Performs DNS lookup and Whois query for a given domain.
    Prioritizes specific fields for owner and provides fallback details.

    Returns:
        dict: {
            'domain': str,
            'ips': list[str],
            'owner': str | None,
            'error': str | None,
            'whois_details': str | None # <-- NEW FIELD
        }
    """
    ips = []
    owner = None
    error_msg = None
    whois_details = None

    # 1. DNS Lookup
    try:
        hostname, aliases, ipaddrlist = socket.gethostbyname_ex(domain)
        ips.extend(ipaddrlist)
        log.debug(f"DNS lookup for {domain} successful: IPs {ips}")

        # 2. Whois Lookup (только если DNS успешен)
        if ips:
            first_ip = ips[0]
            try:
                w = whois.whois(first_ip)
                log.debug(f"Raw Whois response for {first_ip}: {w}")

                # логика извлечения owner
                # приоритетный список полей
                owner_fields_priority = ['org_name', 'org', 'netname', 'descr']
                for field_name in owner_fields_priority:
                    # getattr(w, field_name, None) безопасно вернет None, если поля нет
                    potential_owner = getattr(w, field_name, None)
                    if potential_owner:
                        # Иногда возвращается список, берем первый элемент
                        if isinstance(potential_owner, list):
                            owner = potential_owner[0] if potential_owner else None
                        else:
                            owner = str(potential_owner)  # Убедимся, что это строка

                        if owner:  # Если нашли непустое значение, выходим
                            log.debug(f"Owner found in field '{field_name}': {owner}")
                            break  # Прерываем цикл по полям

                # Если owner все еще не найден, пытаемся угадать по email
                if not owner and w.emails:
                    emails_str = str(w.emails).lower()
                    if "google" in emails_str:
                        owner = "Google LLC"
                    elif "amazon" in emails_str:
                        owner = "Amazon/AWS"
                    elif "cloudflare" in emails_str:
                        owner = "Cloudflare, Inc."

                # Если owner так и не определен, собираем fallback details
                if not owner:
                    owner = "Unknown"
                    details_parts = []
                    # Собираем доп. инфо (безопасно через getattr)
                    mnt_by = getattr(w, 'mnt_by', None)
                    country = getattr(w, 'country', None)
                    # 'route' не является стандартным атрибутом whois-объекта,
                    # он был в сыром тексте RIPE. Мы пока его не можем достать легко.
                    # Вместо него можно взять 'registrar' или 'status'
                    registrar = getattr(w, 'registrar', None)
                    status = getattr(w, 'status', None)

                    if mnt_by: details_parts.append(f"Maintainer: {mnt_by}")
                    if country: details_parts.append(f"Country: {country}")
                    if registrar: details_parts.append(f"Registrar: {registrar}")
                    if status: details_parts.append(f"Status: {status}")

                    if details_parts:
                        whois_details = ", ".join(details_parts)
                        log.debug(f"Owner is Unknown. Fallback details: {whois_details}")
                    else:
                        log.debug("Owner is Unknown. No fallback details found.")

            except Exception as e:
                log.warning(f"Whois lookup failed for {first_ip} (from {domain}): {e}")
                owner = "Whois Error"  # Указываем ошибку Whois

    except socket.gaierror:
        log.warning(f"DNS lookup failed for {domain}: Name or service not known")
        error_msg = "DNS lookup failed"
    except Exception as e:
        log.error(f"Unexpected error during DNS/Whois for {domain}: {e}", exc_info=True)
        error_msg = f"Error: {e}"

    return {
        'domain': domain,
        'ips': ips,
        'owner': owner,
        'error': error_msg,
        'whois_details': whois_details
    }
