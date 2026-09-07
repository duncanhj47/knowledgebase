(function () {
  var STORAGE_KEY = 'dd_recently_viewed';
  var MAX_ITEMS = 5;

  function load() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch (e) {
      return [];
    }
  }

  function save(items) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {}
  }

  function record(id, title, url) {
    var items = load().filter(function (i) { return i.id !== id; });
    items.unshift({ id: id, title: title, url: url });
    save(items.slice(0, MAX_ITEMS));
  }

  function render(excludeId) {
    var container = document.getElementById('recently-viewed');
    if (!container) return;

    var items = load().filter(function (i) { return i.id !== excludeId; });
    if (!items.length) return;

    var html = '<span class="eyebrow">👁 Recently viewed</span><div class="resource-list">';
    items.forEach(function (item) {
      html += '<a class="resource-row" href="' + item.url + '">'
            + '<span class="resource-row-title">' + escapeHtml(item.title) + '</span>'
            + '</a>';
    });
    html += '</div>';
    container.innerHTML = html;
    container.hidden = false;
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  var el = document.getElementById('resource-page-data');
  if (el) {
    // Resource detail page: record this visit, then render history excluding current
    var id = parseInt(el.dataset.resourceId, 10);
    record(id, el.dataset.resourceTitle, el.dataset.resourceUrl);
    render(id);
  } else {
    // Library / other page: render history with nothing excluded
    render(null);
  }
})();
