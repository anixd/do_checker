import requests
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import getpass
import sys

logger = logging.getLogger(__name__)
file_handler = logging.FileHandler("errors.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)
logger.setLevel(logging.ERROR)

def make_request(url, proxy):
    try:
        with requests.Session() as session:
            response = session.get(url, proxies={"http": proxy, "https": proxy}, timeout=20)
        if response.ok:
            data = response.json()
            ip = data["data"]["ip"]
            country_code = data["data"]["country_code"]
            latency = response.elapsed.total_seconds()
            return ip, country_code, latency
    except requests.exceptions.RequestException as e:
        logger.error(f"Error for proxy {proxy}: {e}")
        return None, None, None

def main():
    ports_range = input("Ports range (e.g. 9001-49998): ")
    try:
        start_port, end_port = map(int, ports_range.split('-'))
    except (ValueError, AttributeError):
        print("Error: Invalid ports range format. Use the format 'start-end'.")
        sys.exit(1)

    num_of_requests = input("Requests to make: ")
    login = input("Login: ")
    password = input("Password: ")

    try:
        num_of_requests = int(num_of_requests)
    except ValueError:
        print("Error: Please enter a valid number for the number of requests.")
        sys.exit(1)

    url = "https://checker.soax.com/api/ipinfo"
    host = "proxy.soax.com"

    results = []
    country_codes = {}
    errors = []
    all_ips = []

    time_start = time.monotonic()

    with ThreadPoolExecutor(max_workers=20000) as executor:
        ports = list(range(start_port, end_port + 1))
        for i in range(num_of_requests):
            proxy = f"http://{login}:{password}@{host}:{ports[i % len(ports)]}"
            future = executor.submit(make_request, url, proxy)
            results.append(future)

    success_count = 0
    latencies = []

    for future in as_completed(results):
        ip, country_code, latency = future.result()
        if ip:
            success_count += 1
            all_ips.append(ip)
            if country_code in country_codes:
                country_codes[country_code] += 1
            else:
                country_codes[country_code] = 1
            latencies.append(latency)
        else:
            errors.append(latency)

    time_end = time.monotonic()

    unique_ips = set(all_ips)
    duplicate_ips = len(all_ips) - len(unique_ips)

    success_rate = (success_count / num_of_requests) * 100
    geo_accuracy_representation = " / ".join("{}:{}".format(code, count) for code, count in country_codes.items())

    print("Successful requests: {}".format(success_count))
    print("Errors: {}".format(len(errors)))
    print("Success Rate: {:.2f}%".format(success_rate))
    print("Unique IPs: {}".format(len(unique_ips)))
    print("Duplicate IPs: {}".format(duplicate_ips))
    print("Geo accuracy: {}".format(geo_accuracy_representation))

    if latencies:
        print("Fastest latency: {:.2f} seconds".format(min(latencies)))
        print("Longest latency: {:.2f} seconds".format(max(latencies)))
        print("Average latency: {:.2f} seconds".format(sum(latencies) / len(latencies)))

    print("Time to run: {:.2f} seconds".format(time_end - time_start))

if __name__ == "__main__":
    main()