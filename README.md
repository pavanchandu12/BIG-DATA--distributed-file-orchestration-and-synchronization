# Python Client-Server File Transfer System

This project implements a **secure client-server file transfer system** using Python sockets.  
It allows multiple authenticated users to upload, download, list, preview, and delete files on the server.

---

## ✨ Features

✅ User authentication system  
✅ Upload, download, list, preview, and delete files  
✅ Handles large files efficiently (chunked transfer)  
✅ Length-prefixed JSON messaging for reliable communication  
✅ Multi-client support with threaded server handling  
✅ Clear command-line interface (CLI) for clients  

---

1️⃣ **Clone the repo** 

git clone "url"

cd yourrepo

2️⃣ Start the server

python server.py

3️⃣ Run the client

python client.py

🗂 Available Commands (Client)

Command	Description

login	Authenticate with username+password

upload	Upload a file to the server

download	Download a file from the server

list	List available files

preview	Preview file details

delete	Delete a file

logout	Logout from session


🔒 Security

Length-prefixed JSON messages to ensure correct parsing

Chunked data transfer for handling large files

Multi-threaded server design for handling concurrent clients
