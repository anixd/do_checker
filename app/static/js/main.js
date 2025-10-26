document.addEventListener("DOMContentLoaded", () => {

    // каскадные дропдауны
    const countrySelect = document.getElementById("country");
    const regionSelect = document.getElementById("region");
    const citySelect = document.getElementById("city");
    const ispSelect = document.getElementById("isp");
    
    // получаем URL из data-атрибутов (будут добавлены в html)
    const geoUrls = {
        regions: document.body.dataset.regionsUrl || '/api/geo/regions',
        cities: document.body.dataset.citiesUrl || '/api/geo/cities',
        isps: document.body.dataset.ispsUrl || '/api/geo/isps'
    };
    
    const populateSelect = (selectEl, items, type) => {
      selectEl.innerHTML = '<option value="">(any)</option>';
      if (items && items.length > 0) {
        if (type === 'isp') {
          items.forEach(item => {
            if (typeof item === 'string') {
              const val = item.toLowerCase().replace(/ /g, '+');
              selectEl.add(new Option(item, val));
            }
          });
        } else {
          items.forEach(item => {
            if (item && typeof item === 'object' && item.code && item.name) {
              selectEl.add(new Option(item.name, item.code));
            }
          });
        }
        selectEl.disabled = false;
      } else {
        selectEl.disabled = true;
      }
    };

    if (countrySelect) {
      countrySelect.addEventListener("change", async (e) => {
        const countryCode = e.target.value;
        populateSelect(regionSelect, [], 'region');
        populateSelect(citySelect, [], 'city');
        populateSelect(ispSelect, [], 'isp');
        if (!countryCode) { return; }

        try {
          // используем URL из geoUrls
          const [regionsRes, citiesRes, ispsRes] = await Promise.all([
            fetch(`${geoUrls.regions}?country=${countryCode}`),
            fetch(`${geoUrls.cities}?country=${countryCode}`),
            fetch(`${geoUrls.isps}?country=${countryCode}`)
          ]);
          if (!regionsRes.ok || !citiesRes.ok || !ispsRes.ok) {
             console.error("Failed to fetch geo data: One or more requests failed.");
             return;
          }
          const regions = await regionsRes.json();
          const cities = await citiesRes.json();
          const isps = await ispsRes.json();
          populateSelect(regionSelect, regions, 'region');
          populateSelect(citySelect, cities, 'city');
          populateSelect(ispSelect, isps, 'isp');
        } catch (err) {
          console.error("Failed to fetch geo data:", err);
        }
      });
    }

    // перехват формы и SSE
    const form = document.getElementById("check-form");
    const runButton = document.getElementById("run-button");
    const resultsContainer = document.getElementById("results-container");
    let currentEventSource = null;
    
    // получим URL для EventSource из data-атрибута
    const eventsUrlBase = document.body.dataset.eventsUrl || '/events/'; // базовый URL без run_id

    const renderCard = (payload) => {
        const card = document.createElement("div");
        card.className = "result-card";
        card.id = `result-${payload.run_id}-${payload.url.replace(/[^a-zA-Z0-9]/g, "")}`;
        let icon = "🔄";
        let statusClass = "";
        let statusText = payload.type === 'check_started' ? 'Running...' : payload.result;
        let details = `...`;
        let screenshotHtml = '<div class="screenshot-preview"></div>';
        if (payload.type === 'check_finished') {
            if (payload.result === 'success') {
                icon = "✅"; statusClass = "status-success";
                details = `HTTP ${payload.http_code || 200} | TTFB: ${payload.ttfb_ms || '-'} ms`;
            } else {
                icon = "❌"; statusClass = "status-error";
                details = `Error: ${payload.result} ${payload.http_code ? `(${payload.http_code})` : ''} | ${payload.notes || ''}`;
            }
            if (payload.png_name) {
                const imageUrl = `/logs/${payload.png_name}`;
                screenshotHtml = `
                    <div class="screenshot-preview">
                        <a href="${imageUrl}" target="_blank" title="View full screenshot">
                            <img src="${imageUrl}" alt="Screenshot preview">
                        </a>
                    </div>`;
            } else {
                 screenshotHtml = '<div class="screenshot-preview muted">(no screenshot)</div>';
            }
        }
        card.innerHTML = `
            <div class="status-icon">${icon}</div>
            <div> <strong>${payload.url}</strong> <div class="timings">${details}</div> </div>
            <div class="status ${statusClass}">${statusText}</div>
            ${screenshotHtml}`;
        return card;
     };

    const renderHeader = (payload) => {
        const header = document.createElement("div");
        header.className = "result-header";
        const country = payload.settings?.country?.toUpperCase() || 'N/A';
        const urlCount = payload.settings?.urls ? Object.keys(payload.settings.urls).length : '?';
        header.innerHTML = `
            <strong>Run: <code>${payload.run_id}</code></strong>
            (${country}, ${urlCount} URLs)
            <span id="run-status-${payload.run_id}">(Running...)</span>`;
        return header;
     };

    if (form && runButton) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        runButton.disabled = true; runButton.textContent = "Running...";
        resultsContainer.innerHTML = "";
        if (currentEventSource) { currentEventSource.close(); }

        const formData = new FormData(form);
        let response;
        try {
          response = await fetch(form.action, { method: "POST", body: formData });
        } catch (err) {
          console.error("Fetch error:", err);
          resultsContainer.innerHTML = `<div class="result-card status-error">Network error submitting run.</div>`;
          runButton.disabled = false; runButton.textContent = "Run checks"; return;
        }

        if (!response.ok) {
          let errorMsg = 'Unknown error';
          try { const errData = await response.json(); errorMsg = errData.error || errorMsg; }
          catch(jsonErr) { errorMsg = await response.text(); }
          resultsContainer.innerHTML = `<div class="result-card status-error">Error: ${errorMsg} (${response.status})</div>`;
          runButton.disabled = false; runButton.textContent = "Run checks"; return;
        }

        const data = await response.json();
        const runId = data.run_id;

        // динамически собираем URL для EventSource
        const eventSourceUrl = `${eventsUrlBase}${runId}`;
        currentEventSource = new EventSource(eventSourceUrl);

        currentEventSource.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            if (payload.type === 'run_started') {
                resultsContainer.prepend(renderHeader(payload));
            } else if (payload.type === 'check_started') {
                resultsContainer.append(renderCard(payload));
            } else if (payload.type === 'check_finished') {
                const cardId = `result-${payload.run_id}-${payload.url.replace(/[^a-zA-Z0-9]/g, "")}`;
                const existingCard = document.getElementById(cardId);
                if (existingCard) { existingCard.replaceWith(renderCard(payload)); }
                else { resultsContainer.append(renderCard(payload)); }
            } else if (payload.type === 'run_finished') {
                const statusEl = document.getElementById(`run-status-${payload.run_id}`);
                if (statusEl) { statusEl.textContent = `(Finished in ${payload.totals.time_ms / 1000}s. OK: ${payload.totals.ok}, Err: ${payload.totals.err})`; }
                runButton.disabled = false; runButton.textContent = "Run checks";
                currentEventSource.close();
            }
         };
        currentEventSource.onerror = (err) => {
             console.error("EventSource failed:", err);
             runButton.disabled = false; runButton.textContent = "Run checks";
             if (currentEventSource) currentEventSource.close();
         };
      });
    }

    // Обработка кнопки "Clear logs"
    const clearLogsButton = document.getElementById("clear-logs-button");
    // Получаем URL из data-атрибута
    const clearLogsUrl = clearLogsButton?.dataset.clearUrl || '/logs/clear';

    if (clearLogsButton) {
        clearLogsButton.addEventListener("click", async () => {
            if (!confirm("Are you sure you want to delete all log files? This cannot be undone.")) { return; }
            try {
                // используем URL из clearLogsUrl
                const response = await fetch(clearLogsUrl, { method: "POST" });
                if (response.ok) {
                    alert("Logs cleared successfully.");
                    resultsContainer.innerHTML = '<p class="muted mt-2">Logs cleared.</p>';
                } else {
                    const errData = await response.json();
                    alert(`Error clearing logs: ${errData.message || 'Unknown error'}`);
                }
            } catch (err) {
                console.error("Clear logs fetch error:", err);
                alert("Network error while trying to clear logs.");
            }
        });
    }

  });
