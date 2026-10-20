"""A local-only launcher. Importing the package never opens a microphone."""

import argparse

from dotenv import load_dotenv
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Open THREAD Voice at http://127.0.0.1:8766")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    load_dotenv()
    uvicorn.run("thread_voice.server:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
