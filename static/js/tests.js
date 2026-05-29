window.App = window.App || {};

(function(App) {
  "use strict";

  var stats = { total: 0, running: 0, success: 0, error: 0 };
  var verbose = false;
  var modules = [];
  var testResults = {};

  function apiBase() {
    return App.API;
  }

  function safeId(name) {
    return name.replace(/[\/\\\.]/g, '_');
  }

  async function loadModules() {
    try {
      var resp = await fetch(apiBase() + '/tests/modules');

      if (resp.status === 404) {
        showError('\u274c \u6d4b\u8bd5\u8def\u7531\u672a\u542f\u7528',
          '\u8bf7\u5728 .env \u4e2d\u8bbe\u7f6e ENABLE_TEST_ROUTES=1 \u540e\u91cd\u542f\u670d\u52a1');
        return;
      }
      if (resp.status === 403) {
        showError('\u274c \u6d4b\u8bd5\u8def\u7531\u5df2\u7981\u7528',
          '\u8bf7\u5728 .env \u4e2d\u8bbe\u7f6e ENABLE_TEST_ROUTES=1 \u540e\u91cd\u542f\u670d\u52a1');
        return;
      }

      var data = await resp.json();
      modules = data.modules;

      document.getElementById('totalTests').textContent = data.count;
      stats.total = data.count;

      renderModules();

    } catch (err) {
      console.error('Failed to load modules:', err);
      showError('\u274c \u65e0\u6cd5\u8fde\u63a5\u5230\u540e\u7aef\u670d\u52a1',
        '\u8bf7\u786e\u4fdd\u540e\u7aef\u5df2\u5728\u8fd0\u884c (python start.py)');
    }
  }

  function showError(title, subtitle) {
    var container = document.getElementById('moduleList');
    container.innerHTML = '';
    var errDiv = document.createElement('div');
    errDiv.style.cssText = 'text-align:center;padding:40px;color:#ff4757;';
    errDiv.textContent = title;
    var small = document.createElement('small');
    small.style.cssText = 'color:#a0a0b0;';
    small.textContent = subtitle;
    errDiv.appendChild(document.createElement('br'));
    errDiv.appendChild(small);
    container.appendChild(errDiv);
  }

  function renderModules() {
    var container = document.getElementById('moduleList');
    container.innerHTML = '';

    modules.forEach(function(mod) {
      var section = document.createElement('div');
      section.className = 'module-section';
      section.id = 'module-' + safeId(mod.id);

      var header = document.createElement('div');
      header.className = 'module-header';

      var leftDiv = document.createElement('div');
      leftDiv.className = 'module-header-left';

      var expandBtn = document.createElement('button');
      expandBtn.className = 'expand-btn';
      expandBtn.textContent = '\u25b6';
      expandBtn.addEventListener('click', function() {
        toggleModule(mod.id, expandBtn);
      });
      leftDiv.appendChild(expandBtn);

      var iconSpan = document.createElement('span');
      iconSpan.className = 'module-icon';
      iconSpan.textContent = getModuleIcon(mod.id);
      leftDiv.appendChild(iconSpan);

      var titleDiv = document.createElement('div');
      titleDiv.className = 'module-title';

      var nameSpan = document.createElement('span');
      nameSpan.className = 'module-name';
      nameSpan.textContent = mod.label;
      titleDiv.appendChild(nameSpan);

      var countSpan = document.createElement('span');
      countSpan.className = 'module-count';
      countSpan.textContent = mod.count + ' \u4e2a\u6d4b\u8bd5';
      titleDiv.appendChild(countSpan);

      var badge = document.createElement('span');
      badge.className = 'module-badge';
      badge.id = 'badge-' + safeId(mod.id);
      badge.textContent = '\u23f3 \u5f85\u6d4b';
      titleDiv.appendChild(badge);

      leftDiv.appendChild(titleDiv);
      header.appendChild(leftDiv);

      var runBtn = document.createElement('button');
      runBtn.className = 'test-center-btn test-center-btn-primary module-run-btn';
      runBtn.id = 'modbtn-' + safeId(mod.id);
      runBtn.textContent = '\u25b6 \u4e00\u952e\u6d4b\u8bd5';
      runBtn.addEventListener('click', function() { runModule(mod.id, runBtn); });
      header.appendChild(runBtn);

      section.appendChild(header);

      var body = document.createElement('div');
      body.className = 'module-body';
      body.id = 'modbody-' + safeId(mod.id);

      mod.tests.forEach(function(test) {
        var row = createTestRow(test, mod.id);
        body.appendChild(row);
      });

      section.appendChild(body);
      container.appendChild(section);
    });
  }

  function getModuleIcon(id) {
    var icons = {
      'integration': '\ud83d\udd2c',
      'unit/llm': '\ud83e\udde0',
      'unit/memory': '\ud83d\udcda',
      'unit/systems': '\u2699\ufe0f',
    };
    return icons[id] || '\ud83d\udcc1';
  }

  function toggleModule(moduleId, btn) {
    var body = document.getElementById('modbody-' + safeId(moduleId));
    if (!body) return;
    var expanded = body.classList.toggle('expanded');
    btn.textContent = expanded ? '\u25bc' : '\u25b6';
  }

  function createTestRow(test, moduleId) {
    var row = document.createElement('div');
    row.className = 'test-row';
    row.id = 'row-' + safeId(test.name);

    var leftDiv = document.createElement('div');
    leftDiv.className = 'test-row-left';

    var nameSpan = document.createElement('span');
    nameSpan.className = 'test-row-name';
    nameSpan.textContent = test.name.split('/').pop().replace('.py', '').replace('test_', '');
    leftDiv.appendChild(nameSpan);

    var descSpan = document.createElement('span');
    descSpan.className = 'test-row-desc';
    descSpan.textContent = test.description;
    leftDiv.appendChild(descSpan);

    row.appendChild(leftDiv);

    var rightDiv = document.createElement('div');
    rightDiv.className = 'test-row-right';

    var statusBadge = document.createElement('span');
    statusBadge.className = 'test-row-status';
    statusBadge.id = 'rowstatus-' + safeId(test.name);
    statusBadge.textContent = '\u23f3';
    rightDiv.appendChild(statusBadge);

    var runBtn = document.createElement('button');
    runBtn.className = 'test-center-btn test-center-btn-sm';
    runBtn.id = 'rowbtn-' + safeId(test.name);
    runBtn.textContent = '\u25b6';
    runBtn.addEventListener('click', function() { runSingleTest(test.name, runBtn); });
    rightDiv.appendChild(runBtn);

    row.appendChild(rightDiv);

    var outputSection = document.createElement('div');
    outputSection.className = 'test-row-output';
    outputSection.id = 'rowout-' + safeId(test.name);
    outputSection.setAttribute('data-test-name', test.name);

    var resultBox = document.createElement('pre');
    resultBox.className = 'output-box';
    resultBox.id = 'rowresult-' + safeId(test.name);
    outputSection.appendChild(resultBox);

    row.appendChild(outputSection);

    return row;
  }

  async function runSingleTest(testName, btn) {
    btn.disabled = true;
    btn.textContent = '\u23f3';

    var sid = safeId(testName);
    var statusEl = document.getElementById('rowstatus-' + sid);
    var outputEl = document.getElementById('rowout-' + sid);
    var resultEl = document.getElementById('rowresult-' + sid);

    statusEl.className = 'test-row-status status-running';
    statusEl.textContent = '\u23f3 \u8fd0\u884c\u4e2d';
    outputEl.classList.add('show');
    resultEl.textContent = '\u6b63\u5728\u6267\u884c...';

    stats.running++;
    updateStats();

    try {
      var resp = await fetch(apiBase() + '/tests/run/' + testName, { method: 'POST' });
      var data = await resp.json();
      var elapsed = data.elapsed ? data.elapsed.toFixed(1) : '?';

      testResults[testName] = data;

      if (data.success) {
        statusEl.className = 'test-row-status status-success';
        statusEl.textContent = '\u2705 ' + elapsed + 's';
        stats.success++;
      } else {
        statusEl.className = 'test-row-status status-error';
        statusEl.textContent = '\u274c ' + elapsed + 's';
        stats.error++;
      }

      resultEl.textContent = formatOutput(testName, data, elapsed);

    } catch (err) {
      statusEl.className = 'test-row-status status-error';
      statusEl.textContent = '\u274c \u9519\u8bef';
      resultEl.textContent = '\u8bf7\u6c42\u5931\u8d25: ' + err.message;
      stats.error++;
    }

    stats.running--;
    updateStats();

    btn.disabled = false;
    btn.textContent = '\u25b6';

    updateModuleBadge(testName);
  }

  async function runModule(moduleId, btn) {
    btn.disabled = true;
    btn.textContent = '\u23f3 \u8fd0\u884c\u4e2d...';

    var sid = safeId(moduleId);
    var badge = document.getElementById('badge-' + sid);
    badge.className = 'module-badge badge-running';
    badge.textContent = '\u23f3 \u8fd0\u884c\u4e2d...';

    var body = document.getElementById('modbody-' + sid);
    if (body && !body.classList.contains('expanded')) {
      body.classList.add('expanded');
      var expandBtn = body.parentElement.querySelector('.expand-btn');
      if (expandBtn) expandBtn.textContent = '\u25bc';
    }

    var mod = modules.find(function(m) { return m.id === moduleId; });
    if (mod) {
      mod.tests.forEach(function(t) {
        var statusEl = document.getElementById('rowstatus-' + safeId(t.name));
        if (statusEl) {
          statusEl.className = 'test-row-status status-running';
          statusEl.textContent = '\u23f3';
        }
      });
    }

    stats.running++;
    updateStats();

    try {
      var startTime = Date.now();
      var resp = await fetch(apiBase() + '/tests/run-module/' + moduleId, { method: 'POST' });
      var data = await resp.json();
      var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

      data.results.forEach(function(r) {
        testResults[r.test_name] = r;

        var rsid = safeId(r.test_name);
        var statusEl = document.getElementById('rowstatus-' + rsid);
        var resultEl = document.getElementById('rowresult-' + rsid);
        var outputEl = document.getElementById('rowout-' + rsid);
        var rElapsed = r.elapsed ? r.elapsed.toFixed(1) : '?';

        if (statusEl) {
          if (r.success) {
            statusEl.className = 'test-row-status status-success';
            statusEl.textContent = '\u2705 ' + rElapsed + 's';
            stats.success++;
          } else {
            statusEl.className = 'test-row-status status-error';
            statusEl.textContent = '\u274c ' + rElapsed + 's';
            stats.error++;
          }
        }

        if (resultEl) {
          resultEl.textContent = formatOutput(r.test_name, r, rElapsed);
          if (outputEl && (verbose || !r.success || formatOutput(r.test_name, r, rElapsed).indexOf('\n') > 0)) {
            outputEl.classList.add('show');
          }
        }
      });

      var passed = data.passed;
      var total = data.total;
      if (passed === total) {
        badge.className = 'module-badge badge-success';
        badge.textContent = '\u2705 \u5168\u90e8\u901a\u8fc7 (' + elapsed + 's)';
      } else {
        badge.className = 'module-badge badge-error';
        badge.textContent = '\u274c ' + passed + '/' + total + ' \u901a\u8fc7 (' + elapsed + 's)';
      }

    } catch (err) {
      badge.className = 'module-badge badge-error';
      badge.textContent = '\u274c \u8fd0\u884c\u5931\u8d25';
      stats.error++;
    }

    stats.running--;
    updateStats();

    btn.disabled = false;
    btn.textContent = '\u25b6 \u4e00\u952e\u6d4b\u8bd5';
  }

  async function runAll() {
    var btn = document.getElementById('runAllBtn');
    btn.disabled = true;
    btn.textContent = '\u23f3 \u6d4b\u8bd5\u4e2d...';

    stats.success = 0;
    stats.error = 0;
    stats.running++;
    updateStats();

    modules.forEach(function(mod) {
      var sid = safeId(mod.id);
      var badge = document.getElementById('badge-' + sid);
      if (badge) {
        badge.className = 'module-badge badge-running';
        badge.textContent = '\u23f3 \u8fd0\u884c\u4e2d...';
      }
      mod.tests.forEach(function(t) {
        var statusEl = document.getElementById('rowstatus-' + safeId(t.name));
        if (statusEl) {
          statusEl.className = 'test-row-status status-running';
          statusEl.textContent = '\u23f3';
        }
      });
    });

    try {
      var resp = await fetch(apiBase() + '/tests/run-all', { method: 'POST' });
      var data = await resp.json();

      data.results.forEach(function(r) {
        testResults[r.test_name] = r;

        var rsid = safeId(r.test_name);
        var statusEl = document.getElementById('rowstatus-' + rsid);
        var resultEl = document.getElementById('rowresult-' + rsid);
        var outputEl = document.getElementById('rowout-' + rsid);
        var rElapsed = r.elapsed ? r.elapsed.toFixed(1) : '?';

        if (statusEl) {
          if (r.success) {
            statusEl.className = 'test-row-status status-success';
            statusEl.textContent = '\u2705 ' + rElapsed + 's';
            stats.success++;
          } else {
            statusEl.className = 'test-row-status status-error';
            statusEl.textContent = '\u274c ' + rElapsed + 's';
            stats.error++;
          }
        }

        if (resultEl) {
          resultEl.textContent = formatOutput(r.test_name, r, rElapsed);
          if (outputEl && (verbose || !r.success || formatOutput(r.test_name, r, rElapsed).indexOf('\n') > 0)) {
            outputEl.classList.add('show');
          }
        }
      });

      modules.forEach(function(mod) {
        recalcModuleBadge(mod);
      });

    } catch (err) {
      console.error('Run all failed:', err);
    }

    stats.running--;
    updateStats();

    btn.disabled = false;
    btn.textContent = '\u25b6 \u5168\u90e8\u6d4b\u8bd5';
  }

  function formatOutput(testName, data, elapsed) {
    if (verbose) {
      return '[' + testName + '] \u8017\u65f6: ' + elapsed + 's [\u9000\u51fa\u7801: ' + (data.exit_code ?? '?') + ']\n\n' + data.output;
    }
    if (data.success) {
      var summary = extractSummary(data.output);
      if (summary) {
        return '\u2705 \u901a\u8fc7 (' + elapsed + 's)\n' + summary;
      }
      return '\u2705 \u901a\u8fc7 (' + elapsed + 's)';
    }
    var failInfo = extractFailure(data.output);
    if (failInfo) {
      return '\u274c \u5931\u8d25: ' + failInfo;
    }
    var lines = data.output.trim().split('\n');
    var lastErr = '';
    for (var i = lines.length - 1; i >= 0; i--) {
      if (lines[i].trim()) {
        lastErr = lines[i].trim();
        break;
      }
    }
    return '\u274c \u5931\u8d25: ' + lastErr;
  }

  function extractSummary(output) {
    if (!output) return '';
    var lines = output.trim().split('\n');
    for (var i = lines.length - 1; i >= 0; i--) {
      var line = lines[i].trim();
      if (line.indexOf('passed') >= 0 || line.indexOf('PASSED') >= 0) {
        return line;
      }
    }
    return '';
  }

  function extractFailure(output) {
    if (!output) return '';
    var lines = output.trim().split('\n');
    var failLine = '';
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line.indexOf('FAILED') >= 0) {
        failLine = line;
      }
    }
    if (failLine) return failLine;
    for (var i = lines.length - 1; i >= 0; i--) {
      var line = lines[i].trim();
      if (line && line.indexOf('=') < 0 && line.indexOf('-') !== 0) {
        return line;
      }
    }
    return '';
  }

  function updateModuleBadge(testName) {
    for (var i = 0; i < modules.length; i++) {
      var mod = modules[i];
      for (var j = 0; j < mod.tests.length; j++) {
        if (mod.tests[j].name === testName) {
          recalcModuleBadge(mod);
          return;
        }
      }
    }
  }

  function recalcModuleBadge(mod) {
    var sid = safeId(mod.id);
    var badge = document.getElementById('badge-' + sid);
    if (!badge) return;

    var tested = 0, passed = 0;
    mod.tests.forEach(function(t) {
      if (testResults[t.name]) {
        tested++;
        if (testResults[t.name].success) passed++;
      }
    });

    if (tested === 0) {
      badge.className = 'module-badge';
      badge.textContent = '\u23f3 \u5f85\u6d4b';
    } else if (tested < mod.count) {
      badge.className = 'module-badge badge-running';
      badge.textContent = '\u23f3 ' + passed + '/' + tested + ' \u5df2\u6d4b';
    } else if (passed === mod.count) {
      badge.className = 'module-badge badge-success';
      badge.textContent = '\u2705 \u5168\u90e8\u901a\u8fc7';
    } else {
      badge.className = 'module-badge badge-error';
      badge.textContent = '\u274c ' + passed + '/' + mod.count + ' \u901a\u8fc7';
    }
  }

  function toggleVerbose() {
    verbose = document.getElementById('verboseToggle').checked;

    document.querySelectorAll('.test-row-output').forEach(function(el) {
      var testName = el.getAttribute('data-test-name');
      var resultEl = el.querySelector('.output-box');

      if (!verbose) {
        if (testResults[testName] && testResults[testName].success) {
          el.classList.remove('show');
        }
      } else {
        if (testResults[testName]) {
          el.classList.add('show');
        }
      }

      if (resultEl && testResults[testName]) {
        var r = testResults[testName];
        var e = r.elapsed ? r.elapsed.toFixed(1) : '?';
        resultEl.textContent = formatOutput(testName, r, e);
      }
    });
  }

  function updateStats() {
    var runningEl = document.getElementById('runningCount');
    if (runningEl) runningEl.textContent = stats.running;
    var successEl = document.getElementById('successCount');
    if (successEl) successEl.textContent = stats.success;
    var errorEl = document.getElementById('errorCount');
    if (errorEl) errorEl.textContent = stats.error;
  }

  window.TestCenter = {
    runAll: runAll,
    toggleVerbose: toggleVerbose,
  };

  document.addEventListener('DOMContentLoaded', loadModules);

})(window.App);
