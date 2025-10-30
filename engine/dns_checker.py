import socket
import requests
import json
import os
from datetime import datetime
from ipwhois import IPWhois
from ipwhois.exceptions import BaseIpwhoisException
from logging_.engine_logger import get_engine_logger
from config.loader import ConfigStore
from logging_.md_writer import ensure_day_dir, unique_file_path

log = get_engine_logger()


def _parse_owner_from_whois_data(data: dict, provider_map: dict) -> str:
    """
    Parses RDAP/Whois data and checks against the provider keywords map.
    """
    if not data or not provider_map:
        return "Unknown"

    search_text_parts = []

    net = data.get('network', {})
    search_text_parts.append(str(net.get('name', '')).lower())
    search_text_parts.append(str(net.get('remarks', '')).lower())
    search_text_parts.append(str(data.get('asn_description', '')).lower())

    entities = data.get('entities', [])
    for entity in entities:
        if isinstance(entity, dict):
            contact = entity.get('contact', {})
            search_text_parts.append(str(contact.get('name', '')).lower())
            search_text_parts.append(str(contact.get('organization', '')).lower())

            email = contact.get('email', '')
            if email:
                try:
                    domain_part = email.split('@')[1]
                    search_text_parts.append(domain_part)
                except IndexError:
                    pass

        elif isinstance(entity, str):
            search_text_parts.append(entity.lower())

    full_text = " | ".join(search_text_parts)
    log.debug(f"Whois searchable text: {full_text[:500]}...")

    for provider_name, keywords in provider_map.items():
        for keyword in keywords:
            if keyword.lower() in full_text:
                log.debug(f"Found keyword '{keyword}', identified as '{provider_name}'")
                return provider_name

    log.debug("No provider keywords matched.")
    return "Unknown"


def check_domain_dns_whois(domain: str) -> dict:
    """
    Performs DNS lookup and RDAP/whois query using ipwhois.
    Saves raw whois data to a file.
    """
    ips = []
    owner = "Unknown"
    error_msg = None
    raw_whois_text = ""
    geo_data = {}
    whois_log_path = None
    cfg = ConfigStore.get()

    try:
        provider_map = cfg.dns_checker.provider_keywords
    except Exception:
        log.error("Failed to load provider_keywords from ConfigStore. DNS check might fail.")
        provider_map = {}

    try:
        # DNS Lookup (first step)
        hostname, aliases, ipaddrlist = socket.gethostbyname_ex(domain)
        ips.extend(ipaddrlist)
        log.debug(f"DNS lookup for {domain} successful: IPs {ips}")

        # geolocation & RDAP/Whois Lookup (только если DNS Lookup успешен)
        if ips:
            first_ip = ips[0]
            geo_data = _get_geolocation(first_ip)

            try:
                obj = IPWhois(first_ip)
                data = obj.lookup_rdap(depth=1, inc_raw=True)
                raw_data = data.get('raw')

                file_content = ""
                file_ext = "txt"
                if isinstance(raw_data, dict):
                    file_content = json.dumps(raw_data, indent=2)
                    file_ext = "json"
                elif isinstance(raw_data, str):
                    file_content = raw_data
                else:
                    file_content = "No raw data returned from ipwhois."

                ts = datetime.now().strftime("%H-%M-%S")
                base_name = f"{ts}_{domain}"
                day_dir = ensure_day_dir(cfg.paths.logs_dir)
                log_file = unique_file_path(day_dir, base_name, f"whois.{file_ext}")

                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(file_content)

                whois_log_path = os.path.relpath(log_file, cfg.paths.logs_dir)
                whois_log_path = whois_log_path.replace(os.path.sep, '/')
                raw_whois_text = f"Saved to {whois_log_path}"

                owner = _parse_owner_from_whois_data(data, provider_map)

            except BaseIpwhoisException as e:
                log.warning(f"ipwhois lookup failed for {first_ip} (from {domain}): {e}")
                owner = "Whois Error"
                raw_whois_text = getattr(e, 'message', str(e))
            except Exception as e:
                log.error(f"Unexpected error during ipwhois parse for {first_ip}: {e}", exc_info=True)
                owner = "Whois Parse Error"
                raw_whois_text = str(e)

    except socket.gaierror:
        log.warning(f"DNS lookup failed for {domain}: Name or service not known")
        error_msg = "DNS lookup failed"
    except Exception as e:
        log.error(f"Unexpected error during DNS lookup for {domain}: {e}", exc_info=True)
        error_msg = f"Error: {e}"

    return {
        'domain': domain,
        'ips': ips,
        'owner': owner,
        'error': error_msg,
        'raw_whois_text': raw_whois_text,
        'whois_log_path': whois_log_path,
        'country_name': geo_data.get('country_name'),
        'city': geo_data.get('city')
    }


def _get_geolocation(ip: str) -> dict:
    """
    Gets geolocation data from geolocation-db.com.
    """
    if not ip:
        return {}
    try:
        response = requests.get(f"https://geolocation-db.com/json/{ip}", timeout=5)
        response.raise_for_status()
        data = response.json()
        log.debug(f"Geolocation data for {ip}: {data}")
        return {
            "country_name": data.get("country_name"),
            "city": data.get("city")
        }
    except requests.exceptions.RequestException as e:
        log.warning(f"Error retrieving geolocation data for {ip}: {e}")
        return {}
