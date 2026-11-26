import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    request = Request("http://localhost:8000/api/evaluation/run", method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            print(json.dumps(json.loads(response.read()), ensure_ascii=False, indent=2))
    except HTTPError as error:
        print(f"Evaluation API returned HTTP {error.code}.")
        raise SystemExit(1) from error
    except URLError as error:
        print(f"Could not reach the backend: {error.reason}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
