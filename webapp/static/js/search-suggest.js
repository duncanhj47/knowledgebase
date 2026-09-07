(function () {
  var input = document.getElementById('search-input');
  var box = document.getElementById('search-suggestions');
  var wrap = input ? input.closest('.search-input-wrap') : null;
  if (!input || !box || !wrap) return;

  var suggestUrl = wrap.dataset.suggestUrl;
  var libraryBase = wrap.dataset.libraryBase;

  var debounceTimer = null;
  var activeIndex = -1;
  var items = [];

  var TYPE_ICON = { video: '🎬', photo: '📷', text: '📝', url: '🔗', file: '📄' };

  function closeBox() {
    box.hidden = true;
    box.innerHTML = '';
    activeIndex = -1;
    items = [];
  }

  function renderResults(results) {
    items = results;
    activeIndex = -1;
    if (!results.length) {
      closeBox();
      return;
    }
    box.innerHTML = '';
    results.forEach(function (item, i) {
      var row = document.createElement('a');
      row.className = 'search-suggestion';
      row.href = libraryBase + '/' + item.id;
      row.textContent = (TYPE_ICON[item.type] || '') + ' ' + item.title;
      row.dataset.index = i;
      box.appendChild(row);
    });
    box.hidden = false;
  }

  function fetchSuggestions(query) {
    fetch(suggestUrl + '?q=' + encodeURIComponent(query))
      .then(function (res) { return res.json(); })
      .then(renderResults)
      .catch(closeBox);
  }

  input.addEventListener('input', function () {
    var query = input.value.trim();
    clearTimeout(debounceTimer);
    if (query.length < 2) {
      closeBox();
      return;
    }
    debounceTimer = setTimeout(function () { fetchSuggestions(query); }, 250);
  });

  input.addEventListener('keydown', function (event) {
    if (box.hidden || !items.length) return;
    var rows = box.querySelectorAll('.search-suggestion');

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, rows.length - 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault();
      rows[activeIndex].click();
      return;
    } else if (event.key === 'Escape') {
      closeBox();
      return;
    } else {
      return;
    }

    rows.forEach(function (r, i) { r.classList.toggle('active', i === activeIndex); });
  });

  document.addEventListener('click', function (event) {
    if (event.target !== input && !box.contains(event.target)) {
      closeBox();
    }
  });
})();
