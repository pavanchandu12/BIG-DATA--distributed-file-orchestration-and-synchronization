import socket
import threading
import os
import signal
import sys
import json
import struct
from pathlib import Path

class FileTransferServer:
    def __init__(self, host='localhost', port=9999, storage_root='server_storage'):
        self.host = host
        self.port = port
        self.storage_root = Path(storage_root)
        self.server_socket = None
        self.clients = set()
        self.running = False
        
        # Create storage directory if it doesn't exist
        self.storage_root.mkdir(exist_ok=True)
        
        # Load user credentials
        self.credentials = self.load_credentials()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def load_credentials(self):
        """Load username/password pairs from id_passwd.txt"""
        credentials = {}
        try:
            with open('id_passwd.txt', 'r') as f:
                for line in f:
                    username, password = line.strip().split(':')
                    credentials[username] = password
        except FileNotFoundError:
            print("Warning: id_passwd.txt not found. Creating sample credentials.")
            credentials = {'user1': 'pass1', 'user2': 'pass2'}
            with open('id_passwd.txt', 'w') as f:
                for username, password in credentials.items():
                    f.write(f"{username}:{password}\n")
        return credentials

    def send_message(self, client_socket, message):
        """Send a JSON message with a length prefix"""
        json_data = json.dumps(message).encode()
        length_prefix = struct.pack('!I', len(json_data))
        client_socket.sendall(length_prefix + json_data)

    def receive_message(self, client_socket):
        """Receive a JSON message with a length prefix"""
        try:
            # Receive the length prefix (4 bytes)
            length_data = client_socket.recv(4)
            if not length_data:
                return None
            
            message_length = struct.unpack('!I', length_data)[0]
            
            # Receive the actual message
            message_data = b''
            while len(message_data) < message_length:
                chunk = client_socket.recv(min(4096, message_length - len(message_data)))
                if not chunk:
                    return None
                message_data += chunk
            
            return json.loads(message_data.decode())
        except (struct.error, json.JSONDecodeError) as e:
            print(f"Error receiving message: {e}")
            return None

    def authenticate_client(self, client_socket):
        """Authenticate client using username and password"""
        try:
            auth_data = self.receive_message(client_socket)
            if not auth_data:
                return None
            
            username = auth_data.get('username')
            password = auth_data.get('password')

            if username in self.credentials and self.credentials[username] == password:
                self.send_message(client_socket, {'status': 'success'})
                return username
            else:
                self.send_message(client_socket, {'status': 'failed'})
                return None
        except Exception as e:
            print(f"Authentication error: {e}")
            self.send_message(client_socket, {'status': 'failed', 'message': 'Authentication error'})
            return None

    def send_file(self, client_socket, file_path):
        """Send file data with proper chunking and length prefix"""
        try:
            file_size = file_path.stat().st_size
            self.send_message(client_socket, {'status': 'success', 'size': file_size})
            
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                while bytes_sent < file_size:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    client_socket.sendall(chunk)
                    bytes_sent += len(chunk)
            return True
        except Exception as e:
            print(f"Error sending file: {e}")
            return False

    def handle_client(self, client_socket, addr):
        """Handle individual client connection"""
        username = self.authenticate_client(client_socket)
        if not username:
            client_socket.close()
            return
        
        user_dir = self.storage_root / username
        user_dir.mkdir(exist_ok=True)
        
        self.clients.add(client_socket)
        
        try:
            while self.running:
                data = self.receive_message(client_socket)
                if not data:
                    break
                
                command = data.get('command')
                filename = data.get('filename', '')

                try:
                    if command == 'list':
                        files = [f.name for f in user_dir.iterdir() if f.is_file()]
                        self.send_message(client_socket, {'status': 'success', 'files': files})

                    elif command == 'upload' and filename:
                        file_size = int(data.get('size', 0))
                        file_path = user_dir / filename

                        with open(file_path, 'wb') as f:
                            received = 0
                            while received < file_size:
                                chunk = client_socket.recv(min(4096, file_size - received))
                                if not chunk:
                                    break
                                f.write(chunk)
                                received += len(chunk)

                        self.send_message(client_socket, {'status': 'success', 'message': 'File uploaded successfully'})

                    elif command == 'download' and filename:
                        file_path = user_dir / filename
                        if file_path.exists():
                            self.send_file(client_socket, file_path)
                        else:
                            self.send_message(client_socket, {'status': 'error', 'message': 'File not found'})

                    elif command == 'view' and filename:
                        file_path = user_dir / filename
                        if file_path.exists():
                            with open(file_path, 'rb') as f:
                                preview = f.read(1024)
                            self.send_message(client_socket, {
                                'status': 'success',
                                'preview': preview.decode(errors='ignore')
                            })
                        else:
                            self.send_message(client_socket, {'status': 'error', 'message': 'File not found'})

                    elif command == 'delete' and filename:
                        file_path = user_dir / filename
                        if file_path.exists():
                            file_path.unlink()
                            self.send_message(client_socket, {'status': 'success', 'message': 'File deleted successfully'})
                        else:
                            self.send_message(client_socket, {'status': 'error', 'message': 'File not found'})

                except Exception as e:
                    print(f"Error handling command {command}: {e}")
                    self.send_message(client_socket, {'status': 'error', 'message': str(e)})

        finally:
            self.clients.remove(client_socket)
            client_socket.close()

    def start(self):
        """Start the server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        self.running = True
        print(f"Server started on {self.host}:{self.port}")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"New connection from {addr}")
                thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                thread.daemon = True
                thread.start()
            except socket.error as e:
                print(f"Socket error: {e}")
                break

    def handle_shutdown(self, signum, frame):
        """Handle server shutdown"""
        print("\nShutting down server...")
        self.running = False
        
        # Close all client connections
        for client in list(self.clients):
            try:
                client.close()
            except Exception as e:
                print(f"Error closing client: {e}")
        
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
        
        sys.exit(0)

if __name__ == '__main__':
    server = FileTransferServer()
    server.start()
