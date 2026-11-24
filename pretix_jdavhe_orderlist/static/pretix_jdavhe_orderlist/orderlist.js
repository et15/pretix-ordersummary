/*
 * Live filter for the participant order list.
 *
 * Applies the status filter as soon as it changes and the search while typing,
 * by loading only the result table (see OrderListView) instead of the whole page.
 * Without JavaScript, the form is submitted as usual.
 */
$(function () {
    'use strict'

    const form = document.getElementById('jdavhe-orderlist-filter')
    const results = document.getElementById('jdavhe-orderlist-results')
    if (!form || !results || !window.fetch) {
        return
    }
    const SEARCH_DELAY_MS = 300
    let controller = null
    let timer = null

    function filterUrl () {
        // A changed filter starts on page 1, so "page" is not taken over.
        const params = new URLSearchParams()
        for (const [key, value] of new FormData(form)) {
            if (value !== '') {
                params.append(key, value)
            }
        }
        const query = params.toString()
        return window.location.pathname + (query ? '?' + query : '')
    }

    function load () {
        const url = filterUrl()
        if (controller) {
            controller.abort()
        }
        controller = new AbortController()
        results.setAttribute('aria-busy', 'true')
        results.style.opacity = '0.5'
        fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            signal: controller.signal,
        }).then(function (response) {
            if (!response.ok || response.redirected) {
                // E.g. session expired: let the browser handle it.
                throw new Error('Unexpected response')
            }
            return response.text()
        }).then(function (html) {
            results.innerHTML = html
            // pretix' own initialisation (tooltips, page selection, ...).
            if (typeof setup_basics === 'function') {
                setup_basics($(results))
            }
            window.history.replaceState(null, '', url)
            results.removeAttribute('aria-busy')
            results.style.opacity = ''
        }).catch(function (error) {
            if (error.name !== 'AbortError') {
                window.location.href = url
            }
        })
    }

    form.querySelector('select[name=status]').addEventListener('change', load)
    form.querySelector('input[name=query]').addEventListener('input', function () {
        clearTimeout(timer)
        timer = setTimeout(load, SEARCH_DELAY_MS)
    })
    form.addEventListener('submit', function (event) {
        event.preventDefault()
        clearTimeout(timer)
        load()
    })
})
