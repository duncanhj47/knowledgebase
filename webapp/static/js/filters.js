(function () {
  function initTagFilter(root) {
    var trigger = root.querySelector('.tag-filter-trigger');
    var panel = root.querySelector('.tag-filter-panel');
    var search = root.querySelector('.tag-filter-search');
    var options = Array.prototype.slice.call(root.querySelectorAll('.tag-filter-option'));
    var countEl = root.querySelector('.tag-filter-count');
    var pillsEl = root.querySelector('.tag-filter-pills');

    function refreshPillsAndCount() {
      var checked = options.filter(function (opt) {
        return opt.querySelector('input').checked;
      });

      countEl.textContent = checked.length || '';
      countEl.hidden = checked.length === 0;

      pillsEl.innerHTML = '';
      checked.forEach(function (opt) {
        var input = opt.querySelector('input');
        var label = opt.querySelector('span').textContent;
        var pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'tag-pill tag-pill-removable';
        pill.textContent = label + ' \u00D7';
        pill.setAttribute('aria-label', 'Remove ' + label + ' filter');
        pill.addEventListener('click', function () {
          input.checked = false;
          root.closest('form').submit();
        });
        pillsEl.appendChild(pill);
      });
    }

    function openPanel() {
      panel.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      search.value = '';
      options.forEach(function (opt) { opt.style.display = ''; });
      search.focus();
    }

    function closePanel() {
      panel.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
    }

    trigger.addEventListener('click', function () {
      if (panel.hidden) { openPanel(); } else { closePanel(); }
    });

    document.addEventListener('click', function (event) {
      if (!root.contains(event.target)) { closePanel(); }
    });

    root.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closePanel();
        trigger.focus();
      }
    });

    search.addEventListener('input', function () {
      var term = search.value.trim().toLowerCase();
      options.forEach(function (opt) {
        var text = opt.querySelector('span').textContent.toLowerCase();
        opt.style.display = text.indexOf(term) !== -1 ? '' : 'none';
      });
    });

    options.forEach(function (opt) {
      opt.querySelector('input').addEventListener('change', refreshPillsAndCount);
    });

    refreshPillsAndCount();
  }

  document.querySelectorAll('.tag-filter').forEach(initTagFilter);
})();
