import http.server, socketserver
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("127.0.0.1", 8765), http.server.SimpleHTTPRequestHandler)
httpd.serve_forever()
