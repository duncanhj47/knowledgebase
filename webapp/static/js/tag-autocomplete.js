(function () {
  var input = document.getElementById('tags-input');
  var box = document.getElementById('tags-suggestions');
  if (!input || !box) return;

  var existingTags = [];
  var dataEl = document.getElementById('existing-tags-data');
  if (dataEl) {
    try {
      existingTags = JSON.parse(dataEl.textContent || '[]');
    } catch (e) {
      existingTags = [];
    }
  }

  var activeIndex = -1;
  var matches = [];

  function currentSegmentBounds() {
    var value = input.value;
    var lastComma = value.lastIndexOf(',');
    var start = lastComma === -1 ? 0 : lastComma + 1;
    return { start: start, end: value.length, text: value.slice(start).trim() };
  }

  function alreadyChosen() {
    // Tags before the current (still-being-typed) segment, so we don't
    // suggest something the person already picked.
    var seg = currentSegmentBounds();
    return input.value
      .slice(0, seg.start)
      .split(',')
      .map(function (t) { return t.trim().toLowerCase(); })
      .filter(Boolean);
  }

  function closeBox() {
    box.hidden = true;
    box.innerHTML = '';
    activeIndex = -1;
    matches = [];
  }

  function renderMatches(term) {
    var chosen = alreadyChosen();
    var termLower = term.toLowerCase();
    matches = existingTags.filter(function (name) {
      var lower = name.toLowerCase();
      return lower.indexOf(termLower) !== -1 && chosen.indexOf(lower) === -1;
    }).slice(0, 8);

    if (!matches.length) {
      closeBox();
      return;
    }

    box.innerHTML = '';
    matches.forEach(function (name, i) {
      var row = document.createElement('div');
      row.className = 'search-suggestion';
      row.textContent = name;
      row.dataset.index = i;
      row.addEventListener('mousedown', function (e) {
        // mousedown (not click) so this fires before the input's blur event
        e.preventDefault();
        chooseMatch(name);
      });
      box.appendChild(row);
    });
    activeIndex = -1;
    box.hidden = false;
  }

  function chooseMatch(name) {
    var seg = currentSegmentBounds();
    var before = input.value.slice(0, seg.start).replace(/,\s*$/, '');
    var prefix = before ? before + ', ' : '';
    input.value = prefix + name + ', ';
    closeBox();
    input.focus();
  }

  input.addEventListener('input', function () {
    var seg = currentSegmentBounds();
    if (seg.text.length < 1) {
      closeBox();
      return;
    }
    renderMatches(seg.text);
  });

  input.addEventListener('keydown', function (event) {
    if (box.hidden || !matches.length) return;
    var rows = box.querySelectorAll('.search-suggestion');

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, rows.length - 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault();
      chooseMatch(matches[activeIndex]);
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
