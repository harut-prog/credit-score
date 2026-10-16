"""Sustain prediction traffic through Ingress and report errors/version changes."""

import argparse
import json
import time
import urllib.request

PAYLOAD = {
    "unsecured_lines": 0.3, "age": 35, "past_30_59": 0,
    "past_90": 0, "past_60_89": 0, "debt_ratio": 0.5,
    "monthly_income": 5000, "credit_lines": 5,
    "real_estate": 1, "dependents": 2,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:80")
    parser.add_argument("--host", default="credit.localhost")
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--interval", type=float, default=0.2)
    args = parser.parse_args()
    url = args.url.rstrip("/") + "/v1/predict"
    data = json.dumps(PAYLOAD).encode()
    end = time.monotonic() + args.seconds
    count = errors = 0
    versions = {}
    while time.monotonic() < end:
        try:
            request = urllib.request.Request(
                url, data=data,
                headers={"Host": args.host, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.load(response)
                if response.status != 200 or result["status_code"] != 200:
                    raise ValueError(f"Unexpected response: {result}")
                version = result["model_version"]
                versions[version] = versions.get(version, 0) + 1
                count += 1
        except Exception as exc:
            errors += 1
            print(f"ERROR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(args.interval)
    print(json.dumps({"requests": count, "errors": errors, "versions": versions}), flush=True)
    return int(errors > 0)


if __name__ == "__main__":
    raise SystemExit(main())
