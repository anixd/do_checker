# DutyOps Mirrors Checker (do_checker)

A web application to check the availability of websites ("mirrors") through the SOAX proxy service using specified geographic parameters. The application runs locally using Docker.

## Prerequisites

* **Python 3.12** or higher (been tested on 3.14).
* **Docker:** Ensure Docker is installed and running. Installation instructions: [Get Docker](https://docs.docker.com/get-docker/)
* **Docker Compose:** Usually installed with Docker Desktop. Check with `docker-compose --version`.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/anixd/do_checker.git](https://github.com/anixd/do_checker.git)
    cd do_checker
    ```

2.  **Create the `.env` file:**
    * Copy the `.env.example` file to `.env`:
        ```bash
        cp .env.example .env
        ```
    * **Edit the `.env` file:** This is the primary way to configure the application.
        * **`SOAX_PORT_LOGIN`:** **(Required)** Replace `YOUR_TOKEN` with your **short token (login)** from the SOAX dashboard, used for Port mode.
        * **`SOAX_API_KEY` and `SOAX_PACKAGE_KEY`:** **(Required for Geo Sync)** If you plan to use the Geo catalog update feature ("Refresh from SOAX"), fill these in from your SOAX dashboard.
        * **`DEFAULT_THEME`:** (Optional) Set the default theme for new users. Can be `light`, `dark`, or `auto` (detects system settings). Defaults to `auto`.
        * **`TZ`:** (Optional) Set your local timezone (e.g., `Europe/Kyiv`). Defaults to `UTC`.
        * **`APP_HOST` and `APP_PORT`:** (Optional) Change the host/port. Defaults to `127.0.0.1:8888`.
        * **`MAX_CONCURRENCY`, `MAX_SCREENSHOT_WORKERS`, and timeouts:** You can adjust performance parameters, although, these are **reasonable** defaults, I do not recommend changing them. In any case, change these options only if you understand what you're doing and why. Consider yourself warned ;)

## Running the Application

### Initial Run (First Time)

1.  **Build and run (foreground):**
    * Run the following command in the project's root directory:
        ```bash
        docker-compose up --build
        ```
    * **Note**: *First launch may take 5-8 minutes due to Playwright and Chromium image download.*
    * The `--build` flag is necessary for the first run. This will build the `do-checker:YYYYMMDD` image specified in `docker-compose.yml` and start the container. You will see logs in your terminal.

2.  **Access the application:**
    * Open your web browser and navigate to `http://127.0.0.1:8888` (or the host/port you set in `.env`).

3.  **Stopping (foreground):**
    * Press `Ctrl+C` in the terminal.

### Updating to a New Version

1.  **Pull changes:**
    * Get the latest code from the repository:
        ```bash
        git pull
        ```

2.  **Rebuild the image:**
    * Build the new version of the image (it will get a new image tag based on the `image:` definition in `docker-compose.yml`):
        ```bash
        docker-compose build
        ```

3.  **Restart the application (detached):**
    * Stop the old container and start the new one in the background:
        ```bash
        docker-compose up -d
        ```

4.  **(Optional) Clean up old images:**
    * After you confirm the new version works, you can clean up old, untagged images to save disk space:
        ```bash
        docker image prune
        ```

## First Run: Syncing the Geo Catalog

When the application starts for the first time, it uses an **empty** Geo catalog (`soax_geo.json`). To use the checker, you **must** fetch the Geo data from SOAX first.

**Requires `SOAX_API_KEY` and `SOAX_PACKAGE_KEY` to be set in your `.env` file.**

1.  Open the **Geo Catalog** page.
2.  The list "Keep/Remove existing countries" will be pre-filled with a default list (KZ, AZ, IN, etc.). You can add new ISO-2 codes (e.g., `pl`) or remove unneeded ones using the form. Click **"Save List Changes"**.
3.  Then click the **"Refresh from SOAX (in background)"** button.
4.  Wait 1-2 minutes. The page will show a flash message when started, and the "Generated At" timestamp will update when finished (you may need to refresh the page to see the final result).

Once this is done, the **Checker** page will correctly show countries, regions, cities, and ISPs in the dropdown menus.

## Usage

* **Checker (`/`):**
    * Enter URLs, select Geo Parameters, and run checks. Results appear in real-time via SSE.
* **DNS Tools (`/dns-checker`):**
    * Enter domains (one per line) to perform a DNS lookup and a Whois/RDAP check to identify the hosting provider (based on `provider_keywords` in the config).
* **Geo Catalog (`/catalog`):**
    * View the local cache of Geo data.
    * Manage the country list (add/remove) and run the "Refresh from SOAX" task.
* **Settings (`/settings`):**
    * View and **dangerously** edit the live `app.yaml` config file.

## Configuration Priority

The application loads settings in a specific order. Settings loaded later **override** settings loaded earlier:

1.  **`data/config/app.yaml`:** The base configuration file. It is created on first run if it doesn't exist.
2.  **Environment Variables (`.env` file):** **(Recommended)** Any variable set in `.env` (like `APP_PORT` or `DEFAULT_THEME`) will override the value from `app.yaml`.

---

### Advanced Configuration (`app.yaml`)

While most settings should be managed via `.env`, some complex structures are only available in `data/config/app.yaml`.

#### `http_client:custom_headers`

This section allows you to add custom HTTP headers to *all* checks (both `requests` and Playwright screenshots).

**Important:** The `custom_headers: {}` line is a placeholder. To add headers, you **must remove the `{}`** and indent your headers correctly:

```yaml
http_client:
  user_agent: "Mozilla/5.0..."
  # ...
  # custom_headers: {}  <- REMOVE THIS LINE
  
  # Add headers like this:
  custom_headers:
    X-CF-Bypass: "MySecretToken123"
    Another-Header: "SomeValue"
```

#### `dns_checker:provider_keywords`

This section defines the keywords used by the DNS Tools page to identify a hosting provider from a Whois record.

* The key (e.g., `Cloudflare`) is the display name shown in the UI.
* The value (e.g., `["Cloudflare", "CLOUDFLARE", "CFN"]`) is a list of strings to search for (case-insensitive) in the raw Whois text.

```yaml
dns_checker:
  provider_keywords:
    "Cloudflare": ["Cloudflare", "CLOUDFLARE", "CFN"]
    "Google Cloud": ["Google LLC", "GOOGLE", "GCP"]
    "Amazon AWS": ["Amazon", "AWS", "AMAZON-02", "Amazon Technologies Inc."]
```

## Logs and Data

* **Logs**: All check results (`.md`, `.png`) and the engine.log are stored in the local `./logs/` directory (mounted from `/logs` in the container).
* **Data**: The `app.yaml` config and `soax_geo.json` catalog are stored in the local `./data/` directory.


## Stopping the Application

* Press `Ctrl+C` in the terminal (if running in foreground).
* Run `docker-compose down` (if running in detached mode).
