// Progressive enhancement only: every feature also works without JavaScript.
(function () {
    'use strict';
    var root = document.documentElement;
    root.classList.add('js');

    var SOURCES_KEY = 'cantica.zdroje';
    var cache = new Map(); // url -> Promise<string> (HTML fragment)
    var CACHE_LIMIT = 40;

    function stored(key) {
        try { return window.localStorage.getItem(key); } catch (e) { return null; }
    }

    function store(key, value) {
        try { window.localStorage.setItem(key, value); } catch (e) { /* private mode: not remembered */ }
    }

    // --- sources switch ----------------------------------------------------------------------
    function initSources() {
        var box = document.getElementById('zdroje');
        if (!box) { return; }
        box.checked = stored(SOURCES_KEY) === '1';
        root.classList.toggle('show-sources', box.checked);
        box.addEventListener('change', function () {
            root.classList.toggle('show-sources', box.checked);
            store(SOURCES_KEY, box.checked ? '1' : '0');
        });
    }

    // --- day navigation: fetch ?fragment=1, swap #day, prefetch the neighbours -----------------
    function fragmentUrl(url) {
        var u = new URL(url, window.location.href);
        u.searchParams.set('fragment', '1');
        return u.toString();
    }

    function load(url) {
        var key = fragmentUrl(url);
        if (!cache.has(key)) {
            if (cache.size >= CACHE_LIMIT) { cache.delete(cache.keys().next().value); }
            var request = fetch(key, { credentials: 'same-origin' }).then(function (r) {
                if (!r.ok) { throw new Error(r.status); }
                return r.text();
            });
            request.catch(function () { cache.delete(key); });
            cache.set(key, request);
        }
        return cache.get(key);
    }

    function prefetch(view) {
        view.querySelectorAll('a[data-nav]').forEach(function (a) { load(a.href).catch(function () {}); });
    }

    function render(html, url, push) {
        var container = document.getElementById('day');
        container.innerHTML = html;
        container.classList.remove('is-loading');
        var view = container.querySelector('.day-view');
        if (view) {
            document.title = view.dataset.title || document.title;
            var form = document.querySelector('.diocese-form');
            if (form) { form.action = view.dataset.url; }
            if (push) { window.history.pushState({ day: true }, '', view.dataset.url || url); }
            initDay(view);
            prefetch(view);
        }
    }

    function go(url, push) {
        var container = document.getElementById('day');
        container.classList.add('is-loading');
        load(url).then(function (html) {
            render(html, url, push);
            if (push) { window.scrollTo({ top: 0 }); }
        }).catch(function () { window.location.href = url; });
    }

    function initDay(view) {
        view.querySelectorAll('a[data-nav]').forEach(function (a) {
            a.addEventListener('click', function (event) {
                if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) { return; }
                event.preventDefault();
                go(a.href, true);
            });
        });
        var date = view.querySelector('.date-form input[type="date"]');
        if (date) {
            date.addEventListener('change', function () {
                if (/^\d{4}-\d{2}-\d{2}$/.test(date.value)) { go('/' + date.value + '/', true); }
            });
            date.form.addEventListener('submit', function (event) {
                event.preventDefault();
                if (date.value) { go('/' + date.value + '/', true); }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initSources();
        var diocese = document.getElementById('dieceze');
        if (diocese) {
            diocese.addEventListener('change', function () { diocese.form.submit(); });
        }
        var container = document.getElementById('day');
        if (!container || !window.fetch || !window.history.pushState) { return; }
        var view = container.querySelector('.day-view');
        if (!view) { return; }
        window.history.replaceState({ day: true }, '', window.location.href);
        initDay(view);
        prefetch(view);
        window.addEventListener('popstate', function (event) {
            if (event.state && event.state.day) { go(window.location.href, false); }
        });
    });
}());
