import uvicorn

from . import config


def main():
    print(f"WinRadar đang chạy: http://{config.HOST}:{config.PORT}  (Ctrl+C để tắt)")
    uvicorn.run("winradar.server:app", host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
