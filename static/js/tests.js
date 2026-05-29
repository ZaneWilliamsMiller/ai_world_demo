window.App = window.App || {};

(function(App) {
  "use strict";

  var stats = { total: 0, running: 0, success: 0, error: 0 };

  function apiBase() {
    return App.BACKEND_URL || window.location.origin;
  }

  async function loadTests() {
    try {
      var resp = await fetch(apiBase() + '/api/tests/list');
      var data = await resp.json();

      document.getElementById('totalTests').textContent = data.count;
      stats.total = data.count;

      var grid = document.getElementById('testGrid');
      grid.innerHTML = '';

      data.tests.forEach(function(test) {
        var card = createTestCard(test);
        grid.appendChild(card);
      });

    } catch (err) {
      console.error('Failed to load tests:', err);
      var grid = document.getElementById('testGrid');
      grid.innerHTML = '';
      var errDiv = document.createElement('div');
      errDiv.style.cssText = 'text-align:center;padding:40px;color:#ff4757;';
      errDiv.textContent = '\u274c \u65e0\u6cd5\u8fde\u63a5\u5230\u540e\u7aef\u670d\u52a1';
      var small = document.createElement('small');
      small.style.cssText = 'color:#a0a0b0;';
      small.textContent = '\u8bf7\u786e\u4fdd\u540e\u7aef\u5df2\u5728\u8fd0\u884c (python start.py)';
      errDiv.appendChild(document.createElement('br'));
      errDiv.appendChild(small);
      grid.appendChild(errDiv);
    }
  }

  function createTestCard(test) {
    var card = document.createElement('div');
    card.className = 'test-card';
    card.id = 'card-' + test.name;

    var headerDiv = document.createElement('div');
    headerDiv.className = 'test-header';
    var innerDiv = document.createElement('div');
    var nameDiv = document.createElement('div');
    nameDiv.className = 'test-name';
    nameDiv.textContent = '\ud83d\udccb ' + test.name;
    innerDiv.appendChild(nameDiv);
    var descDiv = document.createElement('div');
    descDiv.className = 'test-desc';
    descDiv.textContent = test.description;
    innerDiv.appendChild(descDiv);
    headerDiv.appendChild(innerDiv);
    card.appendChild(headerDiv);

    var actionsRow = document.createElement('div');
    actionsRow.className = 'actions-row';
    var runBtn = document.createElement('button');
    runBtn.className = 'test-center-btn test-center-btn-primary';
    runBtn.id = 'btn-' + test.name;
    runBtn.textContent = '\u25b6 \u8fd0\u884c\u6d4b\u8bd5';
    runBtn.addEventListener('click', function() { runTest(test.name, runBtn); });
    actionsRow.appendChild(runBtn);
    var toggleBtn = document.createElement('button');
    toggleBtn.className = 'test-center-btn test-center-btn-secondary';
    toggleBtn.textContent = '\ud83d\udcc4 \u663e\u793a/\u9690\u85cf\u8f93\u51fa';
    toggleBtn.addEventListener('click', function() { toggleOutput(test.name); });
    actionsRow.appendChild(toggleBtn);
    card.appendChild(actionsRow);

    var outputSection = document.createElement('div');
    outputSection.className = 'output-section';
    outputSection.id = 'output-' + test.name;
    var outputHeader = document.createElement('div');
    outputHeader.className = 'output-header';
    var outputLabel = document.createElement('span');
    outputLabel.className = 'output-label';
    outputLabel.textContent = '\u6d4b\u8bd5\u8f93\u51fa\uff1a';
    outputHeader.appendChild(outputLabel);
    var statusBadge = document.createElement('span');
    statusBadge.className = 'status-badge';
    statusBadge.id = 'status-' + test.name;
    outputHeader.appendChild(statusBadge);
    outputSection.appendChild(outputHeader);
    var resultBox = document.createElement('pre');
    resultBox.className = 'output-box';
    resultBox.id = 'result-' + test.name;
    resultBox.textContent = '\u7b49\u5f85\u6267\u884c...';
    outputSection.appendChild(resultBox);
    card.appendChild(outputSection);

    return card;
  }

  async function runTest(testName, btn) {
    btn.disabled = true;
    btn.textContent = '';
    var spinner = document.createElement('span');
    spinner.className = 'loading-spinner';
    btn.appendChild(spinner);
    btn.appendChild(document.createTextNode('\u8fd0\u884c\u4e2d...'));

    var outputSection = document.getElementById('output-' + testName);
    var resultBox = document.getElementById('result-' + testName);
    var statusBadge = document.getElementById('status-' + testName);

    outputSection.classList.add('show');
    statusBadge.className = 'status-badge status-running';
    statusBadge.textContent = '\u23f3 \u8fd0\u884c\u4e2d...';
    resultBox.textContent = '\u6b63\u5728\u6267\u884c\u6d4b\u8bd5\uff0c\u8bf7\u7a0d\u5019...';

    stats.running++;
    updateStats();

    try {
      var startTime = Date.now();
      var resp = await fetch(apiBase() + '/api/tests/run/' + testName, { method: 'POST' });
      var data = await resp.json();
      var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

      if (data.success) {
        statusBadge.className = 'status-badge status-success';
        statusBadge.textContent = '\u2705 \u6210\u529f (' + elapsed + 's)';
        stats.success++;
      } else {
        statusBadge.className = 'status-badge status-error';
        statusBadge.textContent = '\u274c \u5931\u8d25 (' + elapsed + 's) [\u9000\u51fa\u7801: ' + data.exit_code + ']';
        stats.error++;
      }

      resultBox.textContent = '[' + testName + '] \u6267\u884c\u8017\u65f6: ' + elapsed + 's\n\n' + data.output;

    } catch (err) {
      statusBadge.className = 'status-badge status-error';
      statusBadge.textContent = '\u274c \u9519\u8bef';
      resultBox.textContent = '\u8bf7\u6c42\u5931\u8d25: ' + err.message;
      stats.error++;
    }

    stats.running--;
    updateStats();

    btn.disabled = false;
    btn.textContent = '\u25b6 \u91cd\u65b0\u8fd0\u884c';
  }

  function toggleOutput(testName) {
    var section = document.getElementById('output-' + testName);
    if (section) section.classList.toggle('show');
  }

  function updateStats() {
    var runningEl = document.getElementById('runningCount');
    if (runningEl) runningEl.textContent = stats.running;
    var successEl = document.getElementById('successCount');
    if (successEl) successEl.textContent = stats.success;
    var errorEl = document.getElementById('errorCount');
    if (errorEl) errorEl.textContent = stats.error;
  }

  document.addEventListener('DOMContentLoaded', loadTests);

})(window.App);
