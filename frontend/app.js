/* SheetBase frontend.
 *
 * No build step and no framework on purpose: this is served by the same FastAPI
 * process as the API, which is what lets the Google OAuth redirect land back on
 * the app instead of dumping JSON on a different port.
 *
 * Sheet contents are third-party data. Everything from the API is written with
 * textContent or createElement - never innerHTML - so a cell containing
 * "<img onerror=...>" is displayed, not executed.
 */
(() => {
    'use strict';

    const API = '/api/v1';
    const TOKEN_KEY = 'sheetbase.token';

    const state = { apis: [], sheets: [], expandedSheet: null };

    // --- token handling ---------------------------------------------------

    // The callback redirects to /#token=... . A fragment is never sent to the
    // server, so the token stays out of access logs and Referer headers.
    function captureTokenFromHash() {
        const match = /token=([^&]+)/.exec(location.hash);
        if (!match) return;
        localStorage.setItem(TOKEN_KEY, decodeURIComponent(match[1]));
        history.replaceState(null, '', location.pathname);
    }

    const getToken = () => localStorage.getItem(TOKEN_KEY);
    const clearToken = () => localStorage.removeItem(TOKEN_KEY);

    // --- api helper -------------------------------------------------------

    async function api(path, options = {}) {
        const headers = Object.assign({}, options.headers);
        const token = getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;
        if (options.body) headers['Content-Type'] = 'application/json';

        const res = await fetch(API + path, Object.assign({}, options, { headers }));

        if (res.status === 401) {
            // Expired or tampered token: drop it and go back to the landing page
            // rather than leaving the user staring at failing panels.
            clearToken();
            render();
            throw new Error('Session expired. Please sign in again.');
        }
        if (!res.ok) {
            let detail = `${res.status} ${res.statusText}`;
            try {
                const body = await res.json();
                if (body.detail) detail = typeof body.detail === 'string'
                    ? body.detail
                    : JSON.stringify(body.detail);
            } catch (_) { /* non-JSON error body, keep the status line */ }
            throw new Error(detail);
        }
        return res.status === 204 ? null : res.json();
    }

    // --- tiny dom helpers -------------------------------------------------

    const $ = (sel) => document.querySelector(sel);

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;  // never innerHTML
        return node;
    }

    let toastTimer;
    function toast(message, kind = 'ok') {
        const node = $('#toast');
        node.textContent = message;
        node.className = `toast ${kind}`;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => node.classList.add('hidden'), 4000);
    }

    const fail = (err) => toast(err.message || String(err), 'error');

    // --- landing vs app ---------------------------------------------------

    function render() {
        const signedIn = Boolean(getToken());
        $('#landing').classList.toggle('hidden', signedIn);
        $('#app').classList.toggle('hidden', !signedIn);
        $('#session').replaceChildren();

        if (signedIn) {
            const out = el('button', 'btn small', 'Sign out');
            out.addEventListener('click', () => { clearToken(); render(); });
            $('#session').append(out);
            loadSheets();
            loadApis();
        }
    }

    // --- 1. GET /sheets and GET /sheets/{id}/tabs -------------------------

    async function loadSheets() {
        const list = $('#sheets-list');
        list.replaceChildren(el('p', 'muted', 'Loading your spreadsheets…'));
        try {
            state.sheets = await api('/sheets');
            renderSheets();
        } catch (err) {
            list.replaceChildren(el('p', 'error-text', err.message));
        }
    }

    function renderSheets() {
        const list = $('#sheets-list');
        list.replaceChildren();

        if (!state.sheets.length) {
            list.append(el('p', 'muted', 'No spreadsheets found in your Drive.'));
            return;
        }

        state.sheets.forEach((sheet) => {
            const row = el('div', 'row');
            const main = el('div', 'row-main');
            main.append(el('div', 'row-title', sheet.name));
            main.append(el('div', 'row-sub mono', sheet.id));

            const pick = el('button', 'btn small', 'Choose tab');
            pick.addEventListener('click', () => toggleTabs(sheet, row, pick));

            row.append(main, pick);
            list.append(row);
        });
    }

    async function toggleTabs(sheet, row, button) {
        const existing = row.nextElementSibling;
        if (existing && existing.classList.contains('tabs-drawer')) {
            existing.remove();
            button.textContent = 'Choose tab';
            return;
        }
        // Only one drawer open at a time - two open drawers make it easy to
        // publish the wrong spreadsheet's tab.
        document.querySelectorAll('.tabs-drawer').forEach((d) => d.remove());
        document.querySelectorAll('#sheets-list .btn.small').forEach((b) => { b.textContent = 'Choose tab'; });

        button.textContent = 'Loading…';
        try {
            const { tabs } = await api(`/sheets/${encodeURIComponent(sheet.id)}/tabs`);
            const drawer = el('div', 'tabs-drawer');
            if (!tabs.length) {
                drawer.append(el('span', 'muted', 'No tabs found.'));
            }
            tabs.forEach((tab) => {
                const chip = el('button', 'chip', tab);
                chip.addEventListener('click', () => publish(sheet, tab, chip));
                drawer.append(chip);
            });
            row.after(drawer);
            button.textContent = 'Hide tabs';
        } catch (err) {
            button.textContent = 'Choose tab';
            fail(err);
        }
    }

    // --- 2. POST /apis ----------------------------------------------------

    async function publish(sheet, tab, chip) {
        const original = chip.textContent;
        chip.disabled = true;
        chip.textContent = 'Publishing…';
        try {
            const created = await api('/apis', {
                method: 'POST',
                body: JSON.stringify({
                    spreadsheet_id: sheet.id,
                    sheet_name: tab,
                    title: `${sheet.name} · ${tab}`,
                }),
            });
            toast(`Published: ${created.endpoint}`);
            await loadApis();
            showPanel('panel-apis');
        } catch (err) {
            fail(err);
        } finally {
            chip.disabled = false;
            chip.textContent = original;
        }
    }

    // --- 3. GET /apis, refresh, delete ------------------------------------

    async function loadApis() {
        try {
            state.apis = await api('/apis');
        } catch (err) {
            $('#apis-list').replaceChildren(el('p', 'error-text', err.message));
            return;
        }
        $('#api-count').textContent = String(state.apis.length);
        renderApis();
        renderApiOptions();
    }

    function renderApis() {
        const list = $('#apis-list');
        list.replaceChildren();

        if (!state.apis.length) {
            list.append(el('p', 'muted', 'Nothing published yet. Pick a sheet on the Publish tab.'));
            return;
        }

        state.apis.forEach((item) => {
            const row = el('div', 'row');
            const main = el('div', 'row-main');
            main.append(el('div', 'row-title', item.title || item.sheet_name));

            const url = location.origin + item.endpoint;
            main.append(el('div', 'row-sub mono', url));
            main.append(el('div', 'row-sub muted', `tab: ${item.sheet_name}`));

            const actions = el('div', 'row-actions');

            const copy = el('button', 'btn small', 'Copy URL');
            copy.addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(url);
                    toast('Endpoint URL copied');
                } catch (_) {
                    toast('Clipboard blocked by the browser', 'error');
                }
            });

            const open = el('a', 'btn small', 'Open');
            open.href = item.endpoint;
            open.target = '_blank';
            open.rel = 'noreferrer';

            const refresh = el('button', 'btn small', 'Clear cache');
            refresh.addEventListener('click', async () => {
                refresh.disabled = true;
                try {
                    await api(`/apis/${encodeURIComponent(item.id)}/refresh`, { method: 'POST' });
                    toast('Cache cleared — next read comes from Google');
                } catch (err) { fail(err); } finally { refresh.disabled = false; }
            });

            const del = el('button', 'btn small danger', 'Delete');
            del.addEventListener('click', async () => {
                // Unpublishing breaks every consumer of that URL, so make it deliberate.
                if (!confirm(`Delete this API?\n\n${url}\n\nAnything calling this URL will start getting 404s.`)) return;
                del.disabled = true;
                try {
                    await api(`/apis/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
                    toast('API deleted');
                    await loadApis();
                } catch (err) { fail(err); del.disabled = false; }
            });

            actions.append(copy, open, refresh, del);
            row.append(main, actions);
            list.append(row);
        });
    }

    // --- 4. GET /data/{id} playground -------------------------------------

    function renderApiOptions() {
        const select = $('#q-api');
        const previous = select.value;
        select.replaceChildren();
        state.apis.forEach((item) => {
            const option = el('option', null, item.title || item.sheet_name);
            option.value = item.id;
            select.append(option);
        });
        if (previous && state.apis.some((a) => a.id === previous)) select.value = previous;
        updateUrlPreview();
    }

    function buildQuery() {
        const params = new URLSearchParams();
        const columns = $('#q-columns').value.trim();
        const orderBy = $('#q-orderby').value.trim();
        const limit = $('#q-limit').value.trim();
        const offset = $('#q-offset').value.trim();

        if (columns) params.set('columns', columns);
        if (orderBy) {
            params.set('order_by', orderBy);
            params.set('order', $('#q-order').value);
        }
        if (limit) params.set('limit', limit);
        if (offset) params.set('offset', offset);

        // Free-form column filters, one per line: Status=active
        $('#q-filters').value.split('\n').forEach((line) => {
            const idx = line.indexOf('=');
            if (idx <= 0) return;
            const key = line.slice(0, idx).trim();
            const value = line.slice(idx + 1).trim();
            if (key) params.set(key, value);
        });

        return params;
    }

    function updateUrlPreview() {
        const id = $('#q-api').value;
        if (!id) { $('#q-url').textContent = 'No API selected'; return; }
        const qs = buildQuery().toString();
        $('#q-url').textContent = `${API}/data/${id}${qs ? '?' + qs : ''}`;
    }

    async function runQuery() {
        const id = $('#q-api').value;
        if (!id) { toast('Publish a sheet first', 'error'); return; }

        const qs = buildQuery().toString();
        const started = performance.now();
        $('#q-result').replaceChildren(el('p', 'muted', 'Running…'));
        $('#q-meta').replaceChildren();

        try {
            // The data endpoint is public by design, so no auth header is needed.
            const res = await fetch(`${API}/data/${encodeURIComponent(id)}${qs ? '?' + qs : ''}`);
            const body = await res.json();
            if (!res.ok) throw new Error(body.detail || `${res.status} ${res.statusText}`);

            const ms = Math.round(performance.now() - started);
            renderMeta(body, ms);
            renderTable(body.data);
        } catch (err) {
            $('#q-result').replaceChildren(el('p', 'error-text', err.message));
        }
    }

    function renderMeta(body, ms) {
        const meta = $('#q-meta');
        meta.replaceChildren();

        // "cache" vs "google" is the whole point of the caching layer, so make
        // it the most visible thing in the response.
        const badge = el('span', `badge ${body.source === 'cache' ? 'cache' : 'google'}`,
            body.source === 'cache' ? 'served from Redis' : 'fetched from Google');
        meta.append(badge);
        meta.append(el('span', 'meta-item', `${ms} ms`));
        meta.append(el('span', 'meta-item', `${body.count} of ${body.total} rows`));
    }

    function renderTable(rows) {
        const container = $('#q-result');
        container.replaceChildren();

        if (!rows || !rows.length) {
            container.append(el('p', 'muted', 'No rows matched.'));
            return;
        }

        // Union of keys: projection can vary per row if a sheet is ragged.
        const headers = [...new Set(rows.flatMap((r) => Object.keys(r)))];

        const table = el('table');
        const thead = el('thead');
        const headRow = el('tr');
        headers.forEach((h) => headRow.append(el('th', null, h)));
        thead.append(headRow);

        const tbody = el('tbody');
        rows.forEach((row) => {
            const tr = el('tr');
            headers.forEach((h) => {
                const value = row[h];
                // textContent, so sheet data can never become markup.
                tr.append(el('td', null, value === undefined || value === null ? '' : String(value)));
            });
            tbody.append(tr);
        });

        table.append(thead, tbody);
        container.append(table);
    }

    // --- panels -----------------------------------------------------------

    function showPanel(panelId) {
        document.querySelectorAll('.tab').forEach((t) => {
            t.classList.toggle('active', t.dataset.panel === panelId);
        });
        document.querySelectorAll('.panel').forEach((p) => {
            p.classList.toggle('hidden', p.id !== panelId);
        });
    }

    // --- wire up ----------------------------------------------------------

    document.querySelectorAll('.tab').forEach((tab) => {
        tab.addEventListener('click', () => showPanel(tab.dataset.panel));
    });

    $('#reload-sheets').addEventListener('click', loadSheets);
    $('#reload-apis').addEventListener('click', loadApis);
    $('#q-run').addEventListener('click', runQuery);

    ['#q-api', '#q-columns', '#q-orderby', '#q-order', '#q-limit', '#q-offset', '#q-filters']
        .forEach((sel) => {
            const node = $(sel);
            node.addEventListener('input', updateUrlPreview);
            node.addEventListener('change', updateUrlPreview);
        });

    captureTokenFromHash();
    render();
})();
