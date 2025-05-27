import socket
import json
import os
import struct
from pathlib import Path

class FileTransferClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.socket = None
        self.download_directory = Path("downloads")
        self.download_directory.mkdir(exist_ok=True)

    def send_message(self, message):
        """Send a JSON message with length prefix"""
        try:
            json_data = json.dumps(message).encode()
            length_prefix = struct.pack('!I', len(json_data))
            self.socket.sendall(length_prefix + json_data)
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def receive_message(self):
        """Receive a JSON message with length prefix"""
        try:
            # Receive the length prefix (4 bytes)
            length_data = self.socket.recv(4)
            if not length_data:
                return None
            
            message_length = struct.unpack('!I', length_data)[0]
            
            # Receive the actual message
            message_data = b''
            while len(message_data) < message_length:
                chunk = self.socket.recv(min(4096, message_length - len(message_data)))
                if not chunk:
                    return None
                message_data += chunk
            
            return json.loads(message_data.decode())
        except (struct.error, json.JSONDecodeError) as e:
            print(f"Error receiving message: {e}")
            return None

    def connect(self, username, password):
        """Connect to server and authenticate"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))

            # Send authentication data
            auth_data = {'username': username, 'password': password}
            self.send_message(auth_data)

            # Receive authentication response
            response = self.receive_message()
            return response and response.get('status') == 'success'
        
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def list_files(self):
        """List files in user's directory"""
        if not self.send_message({'command': 'list'}):
            return []
        
        response = self.receive_message()
        return response.get('files', []) if response and response.get('status') == 'success' else []

    def upload_file(self, filepath):
        """Upload a file to the server"""
        try:
            # Convert string path to Path object
            file_path = Path(filepath)
            
            # Check if file exists
            if not file_path.exists():
                print(f"File not found: {filepath}")
                return False
            
            # Get file details
            filename = file_path.name
            file_size = file_path.stat().st_size

            print(f"Preparing to upload {filename} ({file_size} bytes)")

            # Send upload command with file info
            command = {
                'command': 'upload',
                'filename': filename,
                'size': file_size
            }
            
            if not self.send_message(command):
                print("Failed to send upload command")
                return False

            # Send file data in chunks
            bytes_sent = 0
            chunk_size = 4096

            with open(file_path, 'rb') as f:
                while bytes_sent < file_size:
                    remaining = file_size - bytes_sent
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    
                    self.socket.sendall(chunk)
                    bytes_sent += len(chunk)
                    
                    # Print progress
                    progress = (bytes_sent / file_size) * 100
                    print(f"\rUploading: {progress:.1f}%", end='', flush=True)

            print("\nWaiting for server confirmation...")
            
            # Wait for server confirmation
            response = self.receive_message()
            if response and response.get('status') == 'success':
                print(f"\nUpload completed successfully!")
                return True
            else:
                print(f"\nUpload failed: {response.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"\nUpload error: {e}")
            return False

    def download_file(self, filename):
        """Download a file from the server"""
        try:
            # Send download request
            if not self.send_message({
                'command': 'download',
                'filename': filename
            }):
                return False

            # Get initial response with file size
            response = self.receive_message()
            if not response or response.get('status') != 'success':
                print("Failed to initiate download")
                return False

            file_size = response['size']
            save_path = self.download_directory / filename

            # Receive file data
            with open(save_path, 'wb') as f:
                received_bytes = 0
                while received_bytes < file_size:
                    chunk = self.socket.recv(min(4096, file_size - received_bytes))
                    if not chunk:
                        break
                    f.write(chunk)
                    received_bytes += len(chunk)
                    
                    # Print progress
                    progress = (received_bytes / file_size) * 100
                    print(f"\rDownload progress: {progress:.1f}%", end='')

            print("\nDownload completed!")
            return True

        except Exception as e:
            print(f"\nError during download: {e}")
            return False

    def view_file(self, filename):
        """View first 1024 bytes of a file"""
        if not self.send_message({
            'command': 'view',
            'filename': filename
        }):
            return None

        response = self.receive_message()
        return response.get('preview') if response and response.get('status') == 'success' else None

    def delete_file(self, filename):
        """Delete a file from the server"""
        if not self.send_message({
            'command': 'delete',
            'filename': filename
        }):
            return False

        response = self.receive_message()
        return response and response.get('status') == 'success'

    def close(self):
        """Close the connection"""
        if self.socket:
            try:
                self.socket.close()
                print("Connection closed.")
            except socket.error as e:
                print(f"Error closing connection: {e}")

def main():
    client = FileTransferClient()

    try:
        # Get credentials
        username = input("Username: ")
        password = input("Password: ")

        # Connect and authenticate
        if not client.connect(username, password):
            print("Authentication failed.")
            return

        print("Connected to server!")

        while True:
            print("\nAvailable commands:")
            print("1. List files")
            print("2. Upload file")
            print("3. Download file")
            print("4. View file")
            print("5. Delete file")
            print("6. Exit")

            choice = input("\nEnter choice (1-6): ")

            if choice == '1':
                files = client.list_files()
                if files:
                    print("\nFiles in your directory:")
                    for file in files:
                        print(f"- {file}")
                else:
                    print("No files found or error listing files.")

            elif choice == '2':
                filepath = input("Enter file path to upload: ").strip()
                if not filepath:
                    print("No file path provided.")
                    continue
                if client.upload_file(filepath):
                    print("File uploaded successfully.")
                else:
                    print("Upload failed. Please check if the file exists and try again.")

            elif choice == '3':
                filename = input("Enter filename to download: ")
                if client.download_file(filename):
                    print(f"File downloaded successfully to 'downloads' directory.")
                else:
                    print("Download failed.")

            elif choice == '4':
                filename = input("Enter filename to view: ")
                preview = client.view_file(filename)
                if preview is not None:
                    print("\nFile preview:")
                    print(preview)
                else:
                    print("Failed to view file.")

            elif choice == '5':
                filename = input("Enter filename to delete: ")
                if client.delete_file(filename):
                    print("File deleted successfully.")
                else:
                    print("Delete failed.")

            elif choice == '6':
                break

            else:
                print("Invalid choice.")

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()

if __name__ == '__main__':
    main()
