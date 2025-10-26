# DutyOps Mirrors Checker (do_checker)

A web application to check the availability of websites ("mirrors") through the SOAX proxy service using specified geographic parameters. The application runs locally using Docker.

## Prerequisites

* **Python 3.12** or higher (been tested on 3.14).
* **Docker:** Ensure Docker is installed and running. Installation instructions: [Get Docker](https://docs.docker.com/get-docker/)
* **Docker Compose:** Usually installed with Docker Desktop. Check with `docker-compose --version`.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/anixd/do_checker.git
    cd do_checker
    ```

2.  **Create the `.env` file:**
    * Copy the `.env.example` file to `.env`:
        ```bash
        cp .env.example .env
        ```
    * **Edit the `.env` file:**
        * **`SOAX_PORT_LOGIN`:** Replace `YOUR_TOKEN_HERE` with your **short token (login)** from the SOAX dashboard, used for Port mode. **This is required.**
        * **(Optional) `SOAX_API_KEY` and `SOAX_PACKAGE_KEY`:** If you plan to use the Geo catalog update feature ("Refresh from SOAX"), fill these in from your SOAX dashboard. Remember that `SOAX_PACKAGE_KEY` should contain the same **short token (login)** as `SOAX_PORT_LOGIN`.
        * **(Optional) `APP_HOST` and `APP_PORT`:** You can change the host and port where the application will be accessible. Defaults to `127.0.0.1:8888`.
        * **(Optional) `MAX_CONCURRENCY`, `MAX_SCREENSHOT_WORKERS`, and timeouts:** You can adjust performance parameters, although, these are **reasonable** defaults, I do not recommend changing them. In any case, change these options only if you understand what you're doing and why. Consider yourself warned ;)

## Running the Application

1.  **Initial/Test Run (Foreground):**
    * Run the following command in the project's root directory:
        ```bash
        docker-compose up --build
        ```

    **Note**:  *First launch may take 5-8 minutes due to the pulling and extraction of Playwright and headless Chromium images (they are quite heavy).*
    
    * The `--build` flag is necessary for the first run or if dependencies (`requirements.txt`) or the `Dockerfile` have changed.
    * Docker Compose will build the application image (this might take some time on the first run due to Playwright installation) and start the container. You will see application logs directly in your terminal.
    * To stop the application, press `Ctrl+C`.

2.  **Regular Run (Detached Mode):**
    * For normal use, run the application in the background (detached mode) using the `-d` flag:
        ```bash
        docker-compose up -d
        ```
    * The application will start, and the terminal will be freed up.

3.  **Accessing the Application:**
    * Open your web browser and navigate to the address specified in your `.env` file. It uses the `APP_PORT` variable, **defaulting to `8888`** if not set (e.g., `http://127.0.0.1:8888`).

## Usage

* **Checker Page (`/`):**
    * Enter one or more URLs in the text area (one per line).
    * Select the required **Geo Parameters** (at least "Country").
    * Configure **Proxy Settings** (Protocol, DNS).
    * Use **Advanced / Overrides** if you need to override the proxy host/port or timeout. Enable "Screenshots" or "Debug Mode" as needed.
    * Click "Run checks". Results will appear below the form in real-time.
* **Geo Catalog (`/catalog`):**
    * View the current cache of countries, regions, cities, and ISPs from `data/catalog/soax_geo.json`.
    * The "Refresh from SOAX" button starts a background update of the catalog (requires `SOAX_API_KEY` and `SOAX_PACKAGE_KEY` in `.env`).
* **Settings (`/settings`):**
    * View and edit the application's configuration file `data/config/app.yaml`. **Warning:** Modify settings with caution.

## Logs and Data

* **Check Logs:** Results for each check (`.md` files) and screenshots (`.png`) are saved in the local `./logs/YYYY-MM-DD/` directory within the project dir. This folder is mounted into the container as `/logs`.
* **Engine Log:** The application's technical log (`engine.log`) is located in `./logs/`.
* **Data:** Configuration (`app.yaml`) and the Geo catalog (`soax_geo.json`) are stored in `./data/`. This folder is mounted into the container as `/data`.
* **Clearing Logs:** The "Clear logs" button on the main page deletes all contents of the `./logs/` directory.

## Stopping the Application

* If running in the foreground (`docker-compose up`), press `Ctrl+C`.
* If running in detached mode (`docker-compose up -d`), stop the container using:
    ```bash
    docker-compose down
    ```
* The `docker-compose down` command stops and removes the container but **does not** delete the volumes containing your logs (`./logs/`) and data (`./data/`).

## Configuration Priority

Application settings are loaded in the following order of priority (higher priority overrides lower priority):

1.  **Environment Variables (`.env` file)**
2.  **Configuration File (`data/config/app.yaml`)**

