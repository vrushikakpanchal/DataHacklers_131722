(function (window, document) {
  "use strict";

  var STORAGE_JOB = "secuscribe.currentJob";
  var STORAGE_PENDING = "secuscribe.pending";
  var STORAGE_PROJECTS = "secuscribe.projects";
  var FILE_DB = "secuscribe-files";
  var FILE_STORE = "pending";

  var DELIVERABLES = [
    { id: "social", label: "Social Media Briefs", href: "04_social_media.html" },
    { id: "video", label: "Narrated Video", href: "05_video.html" },
    { id: "advisory", label: "Official Advisory", href: "07_advisory.html" },
    { id: "summary", label: "Executive Summary", href: "06_summary.html" },
    { id: "slides", label: "Presentation Deck", href: "08_slides.html" },
    { id: "infographic", label: "Dynamic Infographics", href: "09_infographic.html" },
  ];

  var SELECT_OPTIONS = {
    audience: [
      "Leadership & Technical Teams",
      "Executive Leadership",
      "Technical / IT Teams",
      "General Public",
      "Students",
    ],
    tone: [
      "Executive / Formal",
      "Urgent Threat Advisory",
      "Public Awareness",
      "Informative",
      "Cybersecurity Technical",
      "Corporate",
    ],
    language: ["English", "Hindi", "Spanish"],
    detail: ["High", "Standard", "Compact", "Concise", "Detailed", "Executive Brief"],
    goal: ["Inform", "Mitigate", "Urgent Action"],
  };

  var DEFAULT_CONFIG = {
    audience: "Leadership & Technical Teams",
    tone: "Executive / Formal",
    language: "English",
    detail: "High",
    goal: "Inform",
  };

  function apiUrl(path) {
    return path;
  }

  function readJson(key) {
    try {
      var raw = sessionStorage.getItem(key) || localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  function writeJson(key, value) {
    var serialized = JSON.stringify(value);
    sessionStorage.setItem(key, serialized);
    localStorage.setItem(key, serialized);
  }

  function openFileDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(FILE_DB, 1);
      req.onupgradeneeded = function () {
        if (!req.result.objectStoreNames.contains(FILE_STORE)) {
          req.result.createObjectStore(FILE_STORE);
        }
      };
      req.onsuccess = function () {
        resolve(req.result);
      };
      req.onerror = function () {
        reject(req.error);
      };
    });
  }

  function savePendingFile(file) {
    if (!file) {
      return Promise.resolve();
    }
    return openFileDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(FILE_STORE, "readwrite");
        tx.objectStore(FILE_STORE).put(file, "current");
        tx.oncomplete = function () {
          resolve();
        };
        tx.onerror = function () {
          reject(tx.error);
        };
      });
    });
  }

  function loadPendingFile() {
    return openFileDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(FILE_STORE, "readonly");
        var req = tx.objectStore(FILE_STORE).get("current");
        req.onsuccess = function () {
          resolve(req.result || null);
        };
        req.onerror = function () {
          reject(req.error);
        };
      });
    });
  }

  function clearPendingFile() {
    return openFileDb().then(function (db) {
      return new Promise(function (resolve) {
        var tx = db.transaction(FILE_STORE, "readwrite");
        tx.objectStore(FILE_STORE).delete("current");
        tx.oncomplete = function () {
          resolve();
        };
        tx.onerror = function () {
          resolve();
        };
      });
    });
  }

  function currentJob() {
    return readJson(STORAGE_JOB);
  }

  function saveJob(job) {
    writeJson(STORAGE_JOB, job);
    var projects = readJson(STORAGE_PROJECTS) || [];
    projects = projects.filter(function (item) {
      return item.job_id !== job.job_id;
    });
    projects.unshift({
      job_id: job.job_id,
      filename: job.filename,
      title: (job.canonical_facts && job.canonical_facts.title) || job.filename,
      created_at: job.created_at,
      status: job.status,
    });
    writeJson(STORAGE_PROJECTS, projects.slice(0, 12));
  }

  function userError(detail) {
    if (!detail) return "The transformation could not be completed.";
    if (typeof detail === "string") return detail;
    if (detail.detail) return String(detail.detail);
    try {
      return JSON.stringify(detail);
    } catch (err) {
      return "The transformation could not be completed.";
    }
  }

  function wordCount(text) {
    var trimmed = (text || "").trim();
    if (!trimmed) return 0;
    return trimmed.split(/\s+/).length;
  }

  function shortHash(hash) {
    if (!hash) return "pending";
    return String(hash).slice(0, 8);
  }

  function formatBytes(bytes) {
    var size = Number(bytes) || 0;
    if (size < 1024) return size + " B";
    if (size < 1024 * 1024) return (size / 1024).toFixed(1) + " KB";
    return (size / (1024 * 1024)).toFixed(1) + " MB";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function selectedFromJob(job) {
    return (job && job.selected_deliverables) || DELIVERABLES.map(function (item) {
      return item.id;
    });
  }

  function firstDeliverableHref(job) {
    var selected = selectedFromJob(job);
    for (var i = 0; i < DELIVERABLES.length; i += 1) {
      if (selected.indexOf(DELIVERABLES[i].id) !== -1) {
        return DELIVERABLES[i].href;
      }
    }
    return "04_social_media.html";
  }

  function showBanner(message, kind) {
    var existing = document.getElementById("secuscribe-banner");
    if (existing) existing.remove();
    var banner = document.createElement("div");
    banner.id = "secuscribe-banner";
    var bg = kind === "error" ? "bg-error-container text-on-error-container" : "bg-secondary-container text-on-surface";
    banner.className =
      "fixed bottom-4 right-4 z-[80] max-w-md px-4 py-3 rounded-xl border-[1.5px] border-primary shadow-[4px_4px_0px_#17161B] font-label-md text-label-md " +
      bg;
    banner.textContent = message;
    document.body.appendChild(banner);
    setTimeout(function () {
      if (banner.parentNode) banner.remove();
    }, 6000);
  }

  function bindBrand() {
    document.title = document.title.replace(/UnifiOps|UNIFIOPS|UniFiOps/gi, "SecuScribe");
  }

  function downloadTextFile(filename, content) {
    var blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function copyText(text, button, labelId) {
    var label = labelId ? document.getElementById(labelId) : button;
    navigator.clipboard.writeText(text || "").then(function () {
      var original = label.textContent;
      label.textContent = "Copied to Clipboard!";
      setTimeout(function () {
        label.textContent = original;
      }, 2000);
    }).catch(function () {
      showBanner("Clipboard copy was blocked by the browser.", "error");
    });
  }

  function requireJob() {
    var job = currentJob();
    if (!job) {
      window.location.href = "02_chat_interface.html";
      return null;
    }
    return job;
  }

  function bindDeliverableNav(activeId) {
    var job = currentJob();
    var selected = selectedFromJob(job);
    document.querySelectorAll("[data-deliverable]").forEach(function (link) {
      var id = link.getAttribute("data-deliverable");
      var meta = DELIVERABLES.find(function (item) {
        return item.id === id;
      });
      if (meta) link.setAttribute("href", meta.href);
      if (job && selected.indexOf(id) === -1) {
        link.classList.add("opacity-40");
      }
      if (id === activeId) {
        link.setAttribute("aria-current", "page");
      }
    });
    var back = document.querySelector("[data-path='deliverables-list'], [data-path='all-deliverables']");
    if (back) back.setAttribute("href", "03_processing.html?view=results");
    var fileChips = document.querySelectorAll("[data-source-filename]");
    fileChips.forEach(function (el) {
      if (job) el.textContent = job.filename;
    });
  }

  function bindSavedProjects(containerSelector) {
    var nav = document.querySelector(containerSelector || "[data-saved-projects]");
    if (!nav) return;
    var projects = readJson(STORAGE_PROJECTS) || [];
    if (!projects.length) {
      nav.innerHTML =
        '<div class="px-3 py-2 rounded-xl border-[1.5px] border-dashed border-primary text-on-surface-variant font-body-sm text-body-sm">No saved transformations yet.</div>';
      return;
    }
    nav.innerHTML = projects
      .map(function (project, index) {
        var active = index === 0 ? "bg-secondary-container border-primary shadow-[2px_2px_0px_#1c1b20]" : "border-transparent";
        return (
          '<a class="flex items-center gap-space-sm px-3 py-2 rounded-xl border-[1.5px] ' +
          active +
          ' text-on-surface font-label-md text-label-md" href="03_processing.html?view=results&job=' +
          encodeURIComponent(project.job_id) +
          '"><span class="material-symbols-outlined text-[18px]">folder</span><span class="truncate">' +
          escapeHtml(project.title || project.filename) +
          "</span></a>"
        );
      })
      .join("");
  }

  function restoreJobFromQuery() {
    var params = new URLSearchParams(window.location.search);
    var jobId = params.get("job");
    if (!jobId) return Promise.resolve(currentJob());
    return fetch(apiUrl("/api/v1/jobs/" + encodeURIComponent(jobId)))
      .then(function (res) {
        if (!res.ok) throw new Error("Saved transformation is unavailable.");
        return res.json();
      })
      .then(function (job) {
        saveJob(job);
        return job;
      })
      .catch(function (err) {
        showBanner(err.message, "error");
        return currentJob();
      });
  }

  function buildDropdown(root, key, label) {
    var options = SELECT_OPTIONS[key] || [];
    var state = readJson("secuscribe.config") || Object.assign({}, DEFAULT_CONFIG);
    var wrap = document.createElement("div");
    wrap.className = "relative inline-block text-left";
    wrap.innerHTML =
      '<button class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-surface-container-lowest border-[1.5px] border-primary text-on-surface font-label-sm text-label-sm transition-all hover:bg-surface-container-low hover:shadow-[2px_2px_0px_#1c1b20]" type="button">' +
      '<span data-select-label>' +
      escapeHtml(label) +
      "</span>" +
      '<span class="material-symbols-outlined text-[14px]">expand_more</span></button>' +
      '<div class="hidden absolute z-30 mt-2 min-w-[220px] rounded-xl border-[1.5px] border-primary bg-surface-container-lowest shadow-[4px_4px_0px_#1c1b20] p-1" data-menu></div>';
    var button = wrap.querySelector("button");
    var menu = wrap.querySelector("[data-menu]");
    var labelEl = wrap.querySelector("[data-select-label]");
    function currentValue() {
      return (readJson("secuscribe.config") || state)[key];
    }
    function render() {
      var value = currentValue();
      labelEl.textContent = label + ": " + value;
      menu.innerHTML = options
        .map(function (option) {
          var active = option === value ? "bg-secondary-container" : "";
          return (
            '<button class="w-full text-left px-3 py-2 rounded-lg font-label-sm text-label-sm hover:bg-surface-container-low ' +
            active +
            '" type="button" data-value="' +
            escapeHtml(option) +
            '">' +
            escapeHtml(option) +
            "</button>"
          );
        })
        .join("");
    }
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      document.querySelectorAll("[data-menu]").forEach(function (other) {
        if (other !== menu) other.classList.add("hidden");
      });
      menu.classList.toggle("hidden");
      render();
    });
    menu.addEventListener("click", function (event) {
      var target = event.target.closest("[data-value]");
      if (!target) return;
      var config = readJson("secuscribe.config") || Object.assign({}, DEFAULT_CONFIG);
      config[key] = target.getAttribute("data-value");
      writeJson("secuscribe.config", config);
      render();
      menu.classList.add("hidden");
    });
    document.addEventListener("click", function () {
      menu.classList.add("hidden");
    });
    render();
    root.replaceWith(wrap);
  }

  function initChat() {
    writeJson("secuscribe.config", readJson("secuscribe.config") || Object.assign({}, DEFAULT_CONFIG));
    bindSavedProjects("nav[data-active-classes]");
    var back = document.querySelector("[data-path='dashboard-home']");
    if (back) back.setAttribute("href", "01_homepage.html");
    var newBtn = document.querySelector("[data-path='new-transformation']");
    if (newBtn) newBtn.setAttribute("href", "02_chat_interface.html");

    var toolbar = document.querySelector(".overflow-x-auto.pb-space-sm");
    if (toolbar) {
      var buttons = toolbar.querySelectorAll("button");
      var map = ["audience", "tone", "language", "detail", "goal"];
      buttons.forEach(function (button, index) {
        if (map[index]) {
          var parent = button.parentElement;
          buildDropdown(parent, map[index], button.textContent.replace(/\s+/g, " ").trim().replace(" expand_more", ""));
        }
      });
    }

    var cards = document.querySelectorAll(".deliverable-card");
    var ids = ["social", "video", "advisory", "summary", "slides", "infographic"];
    cards.forEach(function (card, index) {
      card.setAttribute("data-deliverable-id", ids[index] || "");
      card.classList.add("is-selected");
    });

    window.toggleCard = function (card) {
      var box = card.querySelector(".checkbox-box");
      var icon = card.querySelector(".check-icon");
      var isChecked = !icon.classList.contains("hidden");
      if (isChecked) {
        icon.classList.add("hidden");
        box.classList.remove("bg-tertiary-fixed");
        box.classList.add("bg-surface-container-lowest");
        card.classList.add("opacity-70");
        card.classList.remove("is-selected");
      } else {
        icon.classList.remove("hidden");
        box.classList.add("bg-tertiary-fixed");
        box.classList.remove("bg-surface-container-lowest");
        card.classList.remove("opacity-70");
        card.classList.add("is-selected");
      }
      if (typeof window.updateCounter === "function") window.updateCounter();
    };

    var originalAttach = window.handleFileAttach;
    window.handleFileAttach = function (input) {
      if (typeof originalAttach === "function") originalAttach(input);
      if (input.files && input.files[0]) {
        savePendingFile(input.files[0]);
        writeJson(STORAGE_PENDING, { filename: input.files[0].name, size: input.files[0].size });
      }
    };

    window.removeAttachedFile = function (e) {
      e.stopPropagation();
      var indicator = document.getElementById("fileIndicator");
      indicator.classList.add("hidden");
      indicator.classList.remove("flex");
      var input = document.querySelector('input[type="file"]');
      if (input) input.value = "";
      clearPendingFile();
    };

    window.submitTransformation = function () {
      var input = document.getElementById("promptInput");
      var text = input ? input.value.trim() : "";
      var selected = [];
      document.querySelectorAll(".deliverable-card.is-selected, .deliverable-card:not(.opacity-70)").forEach(function (card) {
        var id = card.getAttribute("data-deliverable-id");
        if (id && selected.indexOf(id) === -1 && !card.querySelector(".check-icon.hidden")) {
          selected.push(id);
        }
      });
      if (!selected.length) {
        selected = ids.slice();
      }
      var fileInput = document.querySelector('input[type="file"]');
      var hasFile = fileInput && fileInput.files && fileInput.files[0];
      if (!hasFile && !text) {
        showBanner("Attach a source file or type transformation instructions first.", "error");
        return;
      }
      var config = readJson("secuscribe.config") || Object.assign({}, DEFAULT_CONFIG);
      var pending = {
        instructions: text,
        selected: selected,
        config: config,
        filename: hasFile ? fileInput.files[0].name : "pasted_source.txt",
        size: hasFile ? fileInput.files[0].size : text.length,
      };
      writeJson(STORAGE_PENDING, pending);
      var proceed = function () {
        window.location.href = "03_processing.html";
      };
      if (hasFile) {
        savePendingFile(fileInput.files[0]).then(proceed).catch(function () {
          showBanner("The selected file could not be stored for processing.", "error");
        });
      } else {
        clearPendingFile().then(proceed);
      }
    };
  }

  function setProcessingCard(id, state, preview, href) {
    var card = document.querySelector('[data-process-card="' + id + '"]');
    if (!card) return;
    var badge = card.querySelector("[data-status-badge]");
    var body = card.querySelector("[data-card-body]");
    var button = card.querySelector("[data-card-action]");
    if (state === "ready") {
      if (badge) {
        badge.className =
          "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#D2FC59] border-[1.5px] border-[#17161B] shadow-[2px_2px_0px_#17161B] font-label-sm text-label-sm uppercase font-extrabold text-on-surface";
        badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-[#17161B]"></span>100% READY';
      }
      if (body) body.innerHTML = preview || "";
      if (button) {
        button.disabled = false;
        button.classList.remove("cursor-not-allowed", "opacity-75", "bg-surface-container-low", "text-on-surface-variant");
        button.classList.add("bg-[#17161B]", "text-on-primary", "shadow-[3px_3px_0px_#DAD9FB]");
        button.innerHTML = '<span>View Output</span><span class="material-symbols-outlined text-[18px]">arrow_forward</span>';
        button.onclick = function () {
          window.location.href = href;
        };
      }
    } else if (state === "error") {
      if (badge) {
        badge.className =
          "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-error-container border-[1.5px] border-[#17161B] font-label-sm text-label-sm uppercase font-extrabold text-on-error-container";
        badge.textContent = "FAILED";
      }
      if (body) body.innerHTML = '<p class="font-body-md text-body-md text-on-error-container">' + escapeHtml(preview || "Generation failed.") + "</p>";
      if (button) {
        button.disabled = true;
        button.textContent = "Unavailable";
      }
    } else {
      if (badge) {
        badge.className =
          "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#DAD9FB] border-[1.5px] border-[#17161B] shadow-[2px_2px_0px_#17161B] font-label-sm text-label-sm uppercase font-extrabold text-[#17161B]";
        badge.innerHTML = '<span class="material-symbols-outlined text-[14px]">bolt</span>GENERATING';
      }
      if (button) {
        button.disabled = true;
        button.classList.add("cursor-not-allowed", "opacity-75");
        button.textContent = "Processing...";
      }
    }
  }

  function applyResultsToProcessing(job) {
    var facts = job.canonical_facts || {};
    var posts = job.social_posts || {};
    var linkedin = posts.linkedin || "";
    var summary = job.executive_summary || facts.summary || "";
    var actions = facts.recommended_actions || [];
    var selected = selectedFromJob(job);
    var errors = job.errors || {};

    document.querySelectorAll("[data-job-filename]").forEach(function (el) {
      el.textContent = job.filename;
    });
    document.querySelectorAll("[data-job-meta]").forEach(function (el) {
      el.textContent = formatBytes(job.file_size) + " • SHA-256 " + shortHash(job.sha256_hash);
    });
    var audience = (job.operator_config || {}).target_audience || "Executive";
    var tone = (job.operator_config || {}).tone || "Formal";
    document.querySelectorAll("[data-job-audience]").forEach(function (el) {
      el.textContent = "Audience: " + audience;
    });
    document.querySelectorAll("[data-job-tone]").forEach(function (el) {
      el.textContent = "Tone: " + tone;
    });

    var readyCount = 0;
    DELIVERABLES.forEach(function (item) {
      if (selected.indexOf(item.id) === -1) {
        setProcessingCard(item.id, "error", "Not requested for this transformation.");
        return;
      }
      if (errors[item.id]) {
        setProcessingCard(item.id, "error", errors[item.id]);
        return;
      }
      readyCount += 1;
      var preview = "";
      if (item.id === "social") preview = '<p class="font-body-md text-body-md text-on-surface leading-relaxed">' + escapeHtml((linkedin || "").slice(0, 220)) + "</p>";
      if (item.id === "video") preview = '<p class="font-body-md text-body-md text-on-surface leading-relaxed">' + escapeHtml(((job.video_package || {}).title || "Video briefing ready.")) + "</p>";
      if (item.id === "advisory") preview = '<p class="font-body-md text-body-md text-on-surface leading-relaxed">' + escapeHtml(facts.summary || "Advisory generated.") + "</p>";
      if (item.id === "summary") {
        preview = actions.slice(0, 3).map(function (action) {
          return '<div class="flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-[#17161B] shrink-0"></span><span class="font-body-md text-body-md text-on-surface font-medium leading-tight">' + escapeHtml(action) + "</span></div>";
        }).join("") || '<p class="font-body-md text-body-md">' + escapeHtml(summary.slice(0, 240)) + "</p>";
      }
      if (item.id === "slides") preview = '<p class="font-body-md text-body-md text-on-surface leading-relaxed">' + escapeHtml(((job.slide_structure || {}).presentation_title || facts.title || "Slide deck ready.")) + "</p>";
      if (item.id === "infographic") {
        var cves = facts.cve_ids || [];
        preview = '<p class="font-body-md text-body-md text-on-surface">Severity ' + escapeHtml(facts.severity || "UNRATED") + (cves[0] ? " • " + escapeHtml(cves[0]) : "") + "</p>";
      }
      setProcessingCard(item.id, "ready", preview, item.href);
    });

    var bar = document.querySelector("[data-bottom-status]");
    if (bar) bar.textContent = readyCount + " of " + selected.length + " outcomes generated";
    var exportBtn = document.querySelector("[data-export-available]");
    if (exportBtn) {
      exportBtn.textContent = "Open Results";
      exportBtn.onclick = function () {
        window.location.href = firstDeliverableHref(job);
      };
    }
    var headerStatus = document.querySelector("[data-header-status]");
    if (headerStatus) headerStatus.innerHTML = '<span class="w-2 h-2 rounded-full bg-[#17161B]"></span><span>Outputs Ready</span>';
  }

  function initProcessing() {
    bindSavedProjects();
    var back = document.querySelector("[data-path='home']");
    if (back) back.setAttribute("href", "01_homepage.html");
    var cancel = document.querySelector("[data-cancel]");
    if (cancel) {
      cancel.addEventListener("click", function () {
        window.location.href = "02_chat_interface.html";
      });
    }

    var params = new URLSearchParams(window.location.search);
    if (params.get("view") === "results") {
      restoreJobFromQuery().then(function (job) {
        if (job) applyResultsToProcessing(job);
      });
      return;
    }

    var pending = readJson(STORAGE_PENDING);
    if (!pending) {
      var existing = currentJob();
      if (existing) {
        applyResultsToProcessing(existing);
        return;
      }
      window.location.href = "02_chat_interface.html";
      return;
    }

    document.querySelectorAll("[data-job-filename]").forEach(function (el) {
      el.textContent = pending.filename || "Source document";
    });
    document.querySelectorAll("[data-job-meta]").forEach(function (el) {
      el.textContent = formatBytes(pending.size) + " • awaiting backend";
    });

    Promise.all([loadPendingFile(), Promise.resolve(pending)]).then(function (parts) {
      var file = parts[0];
      var meta = parts[1];
      var form = new FormData();
      if (file) form.append("file", file, file.name);
      if (meta.instructions) form.append("source_text", meta.instructions);
      if (meta.instructions) form.append("instructions", meta.instructions);
      var config = meta.config || DEFAULT_CONFIG;
      form.append("tone", config.tone);
      form.append("target_audience", config.audience);
      form.append("detail_level", config.detail);
      form.append("language", config.language);
      form.append("goal", config.goal);
      form.append("selected_deliverables", (meta.selected || []).join(","));

      return fetch(apiUrl("/api/v1/transform"), {
        method: "POST",
        body: form,
      }).then(function (res) {
        return res.json().then(function (body) {
          if (!res.ok) throw new Error(userError(body));
          return body;
        });
      });
    }).then(function (job) {
      saveJob(job);
      clearPendingFile();
      applyResultsToProcessing(job);
      if (job.status === "FAILED") {
        showBanner("The backend could not complete this transformation.", "error");
      }
    }).catch(function (err) {
      showBanner(err.message || "Backend unavailable.", "error");
      var bar = document.querySelector("[data-bottom-status]");
      if (bar) bar.textContent = "Transformation failed. Return to chat and try again.";
      document.querySelectorAll("[data-process-card]").forEach(function (card) {
        var id = card.getAttribute("data-process-card");
        setProcessingCard(id, "error", err.message || "Backend unavailable.");
      });
    });
  }

  function socialText(job) {
    var posts = job.social_posts || {};
    var linkedin = posts.linkedin || "";
    var thread = posts.x_thread || [];
    if (Array.isArray(thread) && thread.length) {
      return (linkedin ? linkedin + "\n\n" : "") + thread.join("\n");
    }
    return linkedin;
  }

  function initSocial() {
    var job = requireJob();
    if (!job) return;
    bindDeliverableNav("social");
    var text = socialText(job);
    var textarea = document.getElementById("postSourceInput");
    if (textarea) textarea.value = text || "No social posts were returned by the backend.";
    var badge = document.getElementById("charCountBadge");
    if (badge) badge.textContent = wordCount(textarea.value) + " words • Markdown Mode";
    var hash = document.querySelector("[data-sha-display]");
    if (hash) hash.textContent = "#sha256-" + shortHash(job.sha256_hash);
    var preview = document.getElementById("previewLead");
    if (preview) preview.textContent = (text || "").slice(0, 400);
    var headline = document.getElementById("previewHeadline");
    if (headline && job.canonical_facts) headline.textContent = job.canonical_facts.title || headline.textContent;
    var copyBtn = document.getElementById("btnCopyText");
    if (copyBtn) {
      copyBtn.onclick = function () {
        copyText(textarea.value, copyBtn, "copyBtnText");
      };
    }
    var downloadBtn = document.getElementById("btnDownloadTxt");
    if (downloadBtn) {
      downloadBtn.onclick = function () {
        downloadTextFile("SecuScribe_social_post.txt", textarea.value);
      };
    }
  }

  function initVideo() {
    var job = requireJob();
    if (!job) return;
    bindDeliverableNav("video");
    var pack = job.video_package || {};
    var scenes = pack.scenes || [];
    var list = document.getElementById("scene-list");
    if (list && scenes.length) {
      list.innerHTML = scenes
        .map(function (scene, index) {
          var num = scene.scene_number || index + 1;
          var core = index === 1;
          return (
            '<div class="bg-surface-container-lowest border-[1.5px] border-primary rounded-[8px] p-3.5 shadow-[2px_2px_0px_#1c1b20] flex flex-col gap-2.5">' +
            '<div class="flex items-center justify-between"><span class="px-2.5 py-0.5 ' +
            (core ? "bg-tertiary-fixed text-on-tertiary-fixed border border-primary" : "bg-primary text-on-primary") +
            ' rounded-full font-label-sm text-label-sm font-bold">SCENE ' +
            String(num).padStart(2, "0") +
            (core ? " • CORE" : "") +
            '</span><span class="font-mono font-bold text-label-sm text-on-surface-variant">' +
            escapeHtml(String(scene.duration_seconds || scene.duration || "")) +
            "s</span></div>" +
            '<div class="flex items-center gap-2 bg-surface-container-low border border-primary/20 rounded px-2.5 py-1.5 text-on-surface-variant font-label-sm text-label-sm"><span class="material-symbols-outlined text-[16px] text-primary">smart_display</span><span>Visual Cue: ' +
            escapeHtml(scene.visual_description || scene.on_screen_text || "") +
            "</span></div>" +
            '<div class="p-2.5 bg-surface-container-lowest border border-primary/20 rounded"><p class="font-body-md text-body-md text-on-surface leading-relaxed">' +
            escapeHtml(scene.narration || scene.narration_text || "") +
            "</p></div></div>"
          );
        })
        .join("");
    }
    var title = pack.title || (job.canonical_facts || {}).title || "SecuScribe briefing";
    var overlay = document.getElementById("video-overlay-title");
    if (overlay) overlay.textContent = title;
    var videoEl = document.getElementById("rendered-video");
    var mp4 = job.download_urls && job.download_urls.video_mp4;
    if (videoEl && mp4) {
      videoEl.src = apiUrl(mp4);
      videoEl.classList.remove("hidden");
    }
    var dl = document.getElementById("download-mp4");
    if (dl) {
      if (mp4) {
        dl.href = apiUrl(mp4);
        dl.removeAttribute("download");
      } else {
        dl.addEventListener("click", function (event) {
          event.preventDefault();
          showBanner("No MP4 was generated for this job.", "error");
        });
      }
    }
    var copyBtn = document.getElementById("copy-script-btn");
    if (copyBtn) {
      copyBtn.onclick = function () {
        var script = scenes
          .map(function (scene) {
            return "Scene " + (scene.scene_number || "") + "\n" + (scene.narration || scene.narration_text || "");
          })
          .join("\n\n");
        copyText(script || JSON.stringify(pack, null, 2), copyBtn);
      };
    }
    if (job.errors && job.errors.video) {
      showBanner(job.errors.video, "error");
    }
  }

  function initSummary() {
    var job = requireJob();
    if (!job) return;
    bindDeliverableNav("summary");
    var editor = document.getElementById("executive-markdown-editor");
    var summary = job.executive_summary || (job.canonical_facts || {}).summary || "";
    if (editor) editor.innerText = summary;
    document.querySelectorAll("[data-sha-display]").forEach(function (el) {
      el.textContent = "SHA-256: " + shortHash(job.sha256_hash);
    });
    var facts = job.canonical_facts || {};
    var cards = document.getElementById("summary-preview-cards");
    if (cards) {
      var items = (facts.recommended_actions || []).slice(0, 3);
      if (!items.length && facts.summary) items = [facts.summary];
      cards.innerHTML = items
        .map(function (item) {
          return (
            '<div class="flex items-start gap-3.5 p-3.5 rounded-lg bg-surface-container-lowest border-[1.5px] border-primary"><div class="flex-shrink-0 w-8 h-8 rounded-md bg-tertiary-fixed border-[1.5px] border-primary flex items-center justify-center text-primary shadow-[2px_2px_0px_#1c1b20]"><span class="material-symbols-outlined text-[18px] font-bold">check</span></div><div class="flex flex-col gap-0.5 min-w-0"><span class="font-title-md text-title-md text-primary tracking-tight">' +
            escapeHtml(item) +
            "</span></div></div>"
          );
        })
        .join("");
    }
    var title = document.getElementById("summary-preview-title");
    if (title) title.textContent = facts.title || "Executive Briefing";
    var copyBtn = document.getElementById("copy-markdown-btn");
    if (copyBtn && editor) {
      copyBtn.addEventListener("click", function () {
        copyText(editor.innerText, copyBtn, "copy-btn-label");
      });
    }
    var downloadBtn = document.getElementById("download-summary");
    if (downloadBtn) {
      downloadBtn.addEventListener("click", function () {
        var advisory = job.download_urls && (job.download_urls.advisory);
        if (advisory) {
          window.location.href = apiUrl(advisory);
        } else {
          downloadTextFile("SecuScribe_executive_summary.md", editor ? editor.innerText : summary);
        }
      });
    }
  }

  function initAdvisory() {
    var job = requireJob();
    if (!job) return;
    bindDeliverableNav("advisory");
    var facts = job.canonical_facts || {};
    var root = document.getElementById("advisory-body");
    if (root) {
      root.innerHTML =
        "<h1 class='font-headline-md text-headline-md text-primary mb-2'>" +
        escapeHtml(facts.title || job.filename) +
        "</h1><p class='font-label-md mb-4'>Severity: " +
        escapeHtml(facts.severity || "UNRATED") +
        "</p><p class='font-body-lg text-body-lg mb-6'>" +
        escapeHtml(facts.summary || "") +
        "</p><h2 class='font-title-md mb-2'>Affected systems</h2><p class='mb-4'>" +
        escapeHtml((facts.affected_systems || []).join(", ") || "None listed") +
        "</p><h2 class='font-title-md mb-2'>CVEs</h2><p class='mb-4'>" +
        escapeHtml((facts.cve_ids || []).join(", ") || "None listed") +
        "</p><h2 class='font-title-md mb-2'>Recommended actions</h2><ul class='list-disc pl-5'>" +
        (facts.recommended_actions || [])
          .map(function (item) {
            return "<li class='mb-1'>" + escapeHtml(item) + "</li>";
          })
          .join("") +
        "</ul>";
    }
    var dl = document.getElementById("download-advisory");
    if (dl && job.download_urls && job.download_urls.advisory) {
      dl.href = apiUrl(job.download_urls.advisory);
    }
  }

  function initSlides() {
    var job = requireJob();
    if (!job) return;
    bindDeliverableNav("slides");
    var structure = job.slide_structure || {};
    var slides = structure.slides || [];
    var root = document.getElementById("slides-list");
    if (root) {
      if (!slides.length) {
        root.innerHTML = "<p class='font-body-md'>No slide outline was returned. Download the PPTX if it was generated.</p>";
      } else {
        root.innerHTML = slides
          .map(function (slide) {
            return (
              '<article class="bg-surface-container-lowest border-[1.5px] border-primary rounded-xl p-4 shadow-[3px_3px_0px_#1c1b20]"><div class="font-label-sm uppercase mb-2">Slide ' +
              escapeHtml(slide.slide_number || "") +
              '</div><h3 class="font-headline-sm text-headline-sm mb-2">' +
              escapeHtml(slide.title || "") +
              "</h3><ul class='list-disc pl-5 font-body-md'>" +
              (slide.key_points || [])
                .map(function (point) {
                  return "<li>" + escapeHtml(point) + "</li>";
                })
                .join("") +
              "</ul></article>"
            );
          })
          .join("");
      }
    }
    var dl = document.getElementById("download-pptx");
    if (dl && job.download_urls && job.download_urls.presentation_pptx) {
      dl.href = apiUrl(job.download_urls.presentation_pptx);
    }
  }

  function initInfographic() {
    var job = requireJob();
    if (!job) return;
    bindDeliverableNav("infographic");
    var facts = job.canonical_facts || {};
    var table = document.getElementById("metrics-table");
    if (table) {
      var rows = [
        ["Severity", facts.severity || "UNRATED"],
        ["CVEs", (facts.cve_ids || []).join(", ") || "—"],
        ["Affected systems", (facts.affected_systems || []).join(", ") || "—"],
        ["Locked IPs", (facts.locked_ips || []).join(", ") || "—"],
      ];
      table.innerHTML = rows
        .map(function (row) {
          return "<tr class='border-b border-primary/20'><td class='py-2 pr-4 font-label-md'>" + escapeHtml(row[0]) + "</td><td class='py-2'>" + escapeHtml(row[1]) + "</td></tr>";
        })
        .join("");
    }
    var frame = document.getElementById("svg-frame");
    var svgUrl = job.download_urls && job.download_urls.infographic_svg;
    if (frame && svgUrl) {
      fetch(apiUrl(svgUrl))
        .then(function (res) {
          return res.text();
        })
        .then(function (svg) {
          frame.innerHTML = svg;
        })
        .catch(function () {
          frame.textContent = "Infographic SVG could not be loaded.";
        });
    }
    var dl = document.getElementById("download-svg");
    if (dl && svgUrl) dl.href = apiUrl(svgUrl);
  }

  function initHome() {
    document.querySelectorAll('a[href="02_chat_interface.html"], a[data-path="chat"]').forEach(function (link) {
      link.setAttribute("href", "02_chat_interface.html");
    });
    var generate = document.querySelector('a[href="#"]');
    if (generate && /Generate All 6 Formats/.test(generate.textContent || "")) {
      generate.setAttribute("href", "02_chat_interface.html");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindBrand();
    var page = document.body.getAttribute("data-secuscribe-page") || "";
    if (!page) {
      var file = (window.location.pathname.split("/").pop() || "").toLowerCase();
      if (file.indexOf("01_") === 0 || file === "" || file === "index.html") page = "home";
      else if (file.indexOf("02_") === 0) page = "chat";
      else if (file.indexOf("03_") === 0) page = "processing";
      else if (file.indexOf("04_") === 0) page = "social";
      else if (file.indexOf("05_") === 0) page = "video";
      else if (file.indexOf("06_") === 0) page = "summary";
      else if (file.indexOf("07_") === 0) page = "advisory";
      else if (file.indexOf("08_") === 0) page = "slides";
      else if (file.indexOf("09_") === 0) page = "infographic";
    }
    if (page === "home") initHome();
    if (page === "chat") initChat();
    if (page === "processing") initProcessing();
    if (page === "social") initSocial();
    if (page === "video") initVideo();
    if (page === "summary") initSummary();
    if (page === "advisory") initAdvisory();
    if (page === "slides") initSlides();
    if (page === "infographic") initInfographic();
  });

  window.SecuScribe = {
    currentJob: currentJob,
    saveJob: saveJob,
  };
})(window, document);
