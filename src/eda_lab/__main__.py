from .api import create_server

if __name__ == "__main__":
    server = create_server()
    print("EDA lab API listening on http://127.0.0.1:8080")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
