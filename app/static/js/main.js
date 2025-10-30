document.addEventListener("DOMContentLoaded", () => {

    // получаем URL для EventSource из data-атрибута
    const eventsUrlBase = document.body.dataset.eventsUrl || '/events/'; // базовый URL без run_id

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
    const resetButton = document.getElementById("reset-form-button");
    const runButton = document.getElementById("run-button");
    const resultsContainer = document.getElementById("results-container");
    let currentEventSource = null;

    if (form && resetButton && regionSelect && citySelect && ispSelect) {
        form.addEventListener("reset", (event) => {
            // Стандартный сброс (<input>, <textarea>, <select>) уже произошел.
            // Нам нужно дополнительно обработать зависимые дропдауны.

            // Используем setTimeout, чтобы наш код сработал *после*
            // стандартного сброса браузером.
            setTimeout(() => {
                // Сбрасываем и дизейблим зависимые дропдауны
                populateSelect(regionSelect, [], 'region');
                populateSelect(citySelect, [], 'city');
                populateSelect(ispSelect, [], 'isp');

                // Опционально: Очистить контейнер результатов
                const resultsContainer = document.getElementById("results-container");
                if (resultsContainer) {
                    resultsContainer.innerHTML = '';
                }

                // Опционально: Вернуть фокус на первое поле (textarea)
                const urlsTextarea = document.getElementById("urls");
                if (urlsTextarea) {
                    urlsTextarea.focus();
                }
            }, 0); // Нулевая задержка выполнит код после текущего цикла событий
        });
    }

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

    // DNS checker

    const dnsForm = document.getElementById("dns-check-form");
    const dnsRunButton = document.getElementById("run-dns-check-button");
    const dnsResultsContainer = document.getElementById("dns-results-container");
    let dnsEventSource = null; // Отдельный EventSource для DNS

    // Получаем URL'ы из data-атрибутов
    const checkDnsUrl = document.body.dataset.checkDnsUrl || '/check-dns'; // URL для POST запроса

    const renderDnsCard = (payload) => {
        let icon = "🔄";
        let details = '...';
        let ownerInfo = '...';
        let detailsButtonHtml = '';

        // Находим <div class="dns-result-card"> (если он уже создан)
        // или создаем новый, если это 'dns_check_started'
        const cardId = `dns-result-${payload.run_id}-${payload.domain.replace(/[^a-zA-Z0-9]/g, "")}`;
        let card = document.getElementById(cardId);
        if (!card) {
             card = document.createElement("div");
             card.className = "dns-result-card";
             card.id = cardId;
        }

        if (payload.type === 'dns_check_finished') {
            if (payload.error) {
                icon = "❌";
                details = `<span class="text-danger">${payload.error}</span>`;
                ownerInfo = '-';
            } else {
                icon = "✅";

                // geolocation
                const ipsText = payload.ips && payload.ips.length > 0
                                ? payload.ips.join(', ')
                                : '(No IPs found)';
                let geoText = '';

                // Формируем текст геолокации
                let geoLabel = '<span class="muted">Geo:</span>';
                let geoInfo = '';
                if (payload.city && payload.country_name) {
                    geoInfo = `${payload.city}, ${payload.country_name}`;
                } else if (payload.country_name) {
                    geoInfo = payload.country_name;
                } else if (payload.ips && payload.ips.length > 0) {
                    // Если есть IP, но нет geo -- "Not found"
                    geoInfo = '<span class="muted">Not found</span>';
                }

                if (geoInfo) {
                     geoText = `<div class="ips-list" style="color: #005a9c;">${geoLabel} ${geoInfo}</div>`;
                }

                details = `<div class="ips-list">IPs: ${ipsText}</div>${geoText}`;

                let ownerText = payload.owner || 'Unknown';
                if (ownerText === 'Whois Error' || ownerText === 'Whois Parse Error') {
                    ownerInfo = `<span class="text-danger">${ownerText}</span>`;
                } else {
                    ownerInfo = ownerText;
                }
            }

            // whois_log_path
            if (payload.whois_log_path) {
                // Ссылка на статический файл, который отдает /logs/
                const fileUrl = `/logs/${payload.whois_log_path}`;
                detailsButtonHtml = `<a href="${fileUrl}" target="_blank" rel="noopener noreferrer" class="btn-details">Details</a>`;
            } else if (payload.type === 'dns_check_finished') {
                detailsButtonHtml = `<span class="muted">(no data)</span>`;
            }

        } else if (payload.type === 'dns_check_started') {
             // Для 'started' оставляем плейсхолдеры
             details = '<span class="muted">Resolving DNS...</span>';
             ownerInfo = '<span class="muted">...</span>';
             detailsButtonHtml = '<span class="muted">...</span>';
        }

        card.innerHTML = `
            <div class="status-icon">${icon}</div>
            <div> 
                <strong>${payload.domain}</strong> 
                ${details}
            </div>
            <div class="owner-info">${ownerInfo}</div>
            <div class="details-link">${detailsButtonHtml}</div>
            `;
        return card;
     };

    const renderDnsHeader = (payload) => {
        const header = document.createElement("div");
        header.className = "dns-result-header";
        const domainCount = payload.total_domains || '?';
        header.innerHTML = `
            <strong>DNS Run: <code>${payload.run_id}</code></strong>
            (${domainCount} Domains)
            <span id="dns-run-status-${payload.run_id}">(Running...)</span>`;
        return header;
     };

    if (dnsForm && dnsRunButton) {
      dnsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        dnsRunButton.disabled = true; dnsRunButton.textContent = "Running...";
        dnsResultsContainer.innerHTML = ""; // Очищаем предыдущие результаты
        if (dnsEventSource) { dnsEventSource.close(); } // Закрываем старый SSE, если был

        const formData = new FormData(dnsForm);
        let response;
        try {
          // Используем URL из data-атрибута
          response = await fetch(checkDnsUrl, { method: "POST", body: formData });
        } catch (err) {
          console.error("DNS Check Fetch error:", err);
          dnsResultsContainer.innerHTML = `<div class="dns-result-card status-error">Network error submitting DNS run.</div>`;
          dnsRunButton.disabled = false; dnsRunButton.textContent = "Run DNS check";
          return;
        }

        if (!response.ok) {
          let errorMsg = 'Unknown error';
          try {
              const errData = await response.json();
              errorMsg = errData.error || errorMsg;
          } catch(jsonErr) {
              errorMsg = await response.text();
          }
          dnsResultsContainer.innerHTML = `<div class="dns-result-card status-error">Error: ${errorMsg} (${response.status})</div>`;
          dnsRunButton.disabled = false; dnsRunButton.textContent = "Run DNS check";
          return;
        }

        const data = await response.json();
        const runId = data.run_id;

        // Собираем URL для EventSource
        const eventSourceUrl = `${eventsUrlBase}${runId}`;
        dnsEventSource = new EventSource(eventSourceUrl);

        dnsEventSource.onmessage = (event) => {
            const payload = JSON.parse(event.data);

            // Обрабатываем события *только* для DNS чекера
            if (payload.type === 'dns_run_started') {
                dnsResultsContainer.prepend(renderDnsHeader(payload));
            } else if (payload.type === 'dns_check_started') {
                dnsResultsContainer.append(renderDnsCard(payload));
            } else if (payload.type === 'dns_check_finished') {
                const cardId = `dns-result-${payload.run_id}-${payload.domain.replace(/[^a-zA-Z0-9]/g, "")}`;
                const existingCard = document.getElementById(cardId);
                if (existingCard) {
                    existingCard.replaceWith(renderDnsCard(payload));
                } else {
                    dnsResultsContainer.append(renderDnsCard(payload));
                }
            } else if (payload.type === 'dns_run_finished') {
                const statusEl = document.getElementById(`dns-run-status-${payload.run_id}`);
                if (statusEl) {
                     statusEl.textContent = ` (Finished in ${payload.totals.time_ms / 1000}s. OK: ${payload.totals.ok}, Err: ${payload.totals.err})`;
                }
                dnsRunButton.disabled = false; dnsRunButton.textContent = "Run DNS check";
                dnsEventSource.close();
            }
            // Другие типы событий (от основного чекера) игнорируем
         };

        dnsEventSource.onerror = (err) => {
             console.error("DNS EventSource failed:", err);
             dnsRunButton.disabled = false; dnsRunButton.textContent = "Run DNS check";
             if (dnsEventSource) dnsEventSource.close();
         };
      });
    }

  });
