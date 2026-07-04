# 🐳 Neaty File Organizer Agent - Docker Guide

This guide explains how to build, run, and share **Neaty File Organizer Agent** using Docker. By containerizing the application, you can run Neaty on any computer (Windows, macOS, or Linux) with zero local dependencies aside from Docker itself.

---

## 🏗️ How it Works

Because Docker containers have isolated filesystems, we use **Docker Volumes** to safely bridge your host computer's files with the agent inside the container. 

In our Docker configuration, **we mount your entire Home Directory (`~`) to `/data` inside the container.** This gives Neaty access to almost every folder on your computer (Downloads, Desktop, Documents, etc.) through `/data`.

```mermaid
graph TD
    subgraph Host Computer (User Home Directory)
        Home["Home Folder (~)"]
        Downloads["~/Downloads"]
        Desktop["~/Desktop"]
        Docs["~/Documents"]
    end

    subgraph Docker Container
        ContainerApp["Neaty Web Server (/app)"]
        MountedData["/data"]
        MountedDownloads["/data/Downloads"]
        MountedDesktop["/data/Desktop"]
        MountedDocs["/data/Documents"]
    end

    Home <--> MountedData
    Downloads <--> MountedDownloads
    Desktop <--> MountedDesktop
    Docs <--> MountedDocs
```

1. **Mounting:** Your host computer's Home Directory (`~`) is mapped to `/data` inside the container automatically.
2. **Accessing:** To organize any folder, simply prepend `/data/` to the folder's name relative to your home folder.
3. **Safety:** Neaty scans and organizes those files directly on your host computer, with zero file-transfer lag!

---

## 🚀 Quick Start (Using Docker Compose)

The easiest way to run Neaty is with **Docker Compose**. It handles building the container, exposing the network ports, mounting your home directory, and injecting your API key automatically.

### 1. Configure your Environment
Create a `.env` file in the same directory as `docker-compose.yml` (or rename/use your existing one) and add your Gemini API Key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Spin up the Container
Run the following command in your terminal:
```bash
docker compose up --build
```

### 3. Open the Web UI
Go to **[http://localhost:5050](http://localhost:5050)** in your browser.

Now, you can type **any path** inside your home directory by starting with `/data`. For example:

| To Organize... | Type this in the **Source Directory** box: |
| :--- | :--- |
| **Downloads Folder** | `/data/Downloads` |
| **Desktop Folder** | `/data/Desktop` |
| **Documents Folder** | `/data/Documents` |
| **A Custom Folder inside Documents** | `/data/Documents/MyMessyFolder` |

- **Destination Directory:** Leave empty or set to `/data/Downloads/organized` (it defaults to `organized_output` inside your source folder).
- Click **Scan** or **Organize**!

---

## 🛠️ Alternative: Manual Docker CLI

If you prefer to use the Docker CLI directly without Docker Compose, you can build and run it manually:

### 1. Build the Docker Image
```bash
docker build -t neaty-agent .
```

### 2. Run the Container
Replace `/path/to/your/messy/folder` with the absolute path of the directory you want to organize:

#### **Windows (PowerShell)**
```powershell
docker run -p 5050:5050 `
  -e GEMINI_API_KEY="your_api_key_here" `
  -v "C:\Users\YourUsername:/data" `
  neaty-agent
```

#### **macOS / Linux (Bash)**
```bash
docker run -p 5050:5050 \
  -e GEMINI_API_KEY="your_api_key_here" \
  -v "~:/data" \
  neaty-agent
```

---

## 📦 Sharing the Project with Others

To share this project with a colleague or friend so they can run it without installing Python or dependencies:

1. **Send them the project files:** You can zip the project directory (excluding `.venv`, `__pycache__`, and `.git` folders) and send it to them.
2. **They only need to:**
   - Install **Docker Desktop**.
   - Extract the files.
   - Create a `.env` file with their `GEMINI_API_KEY`.
   - Run `docker compose up --build`.

It's that simple! 🚀
