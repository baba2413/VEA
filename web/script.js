//캐시 변수
const summaryCache = new Map();

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";
  const u = ["B","KB","MB","GB","TB"];
  let i = 0, n = bytes;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2)} ${u[i]}`;
}

// Convert 0/1 to O/X for display
function toOX(value) {
  if (value === 0) return "X";
  if (value === 1) return "O";
  return "-"; // For undefined or other values
}

function formatTime(secs) {
  if (!Number.isFinite(secs)) return "길이 계산 중…";
  const s = Math.floor(secs % 60).toString().padStart(2, "0");
  const m = Math.floor((secs / 60) % 60).toString().padStart(2, "0");
  const h = Math.floor(secs / 3600);
  return h ? `${h}:${m}:${s}` : `${m}:${s}`;
}

const els = {
  loadBtn: document.getElementById("loadBtn"),
  fileInput: document.getElementById("fileInput"),
  videoList: document.getElementById("videoList"),
  videoCount: document.getElementById("videoCount"),
  player: document.getElementById("player"),
};

const state = {
  items: [],
  oxChanges: {}
};

// Add error handler for video player
els.player.addEventListener("error", (e) => {
  console.error("Video playback error:", e);
  console.error("Error code:", els.player.error?.code);
  console.error("Error message:", els.player.error?.message);
  console.error("Current src:", els.player.src);
});

els.loadBtn.addEventListener("click", () => els.fileInput.click());

els.fileInput.addEventListener("change", (e) => {
  const files = Array.from(e.target.files || []);
  const videos = files.filter(f => f.type.startsWith("video/"));
  if (!videos.length) return;

  const existingKey = new Set(state.items.map(i => `${i.file.name}-${i.file.size}`));

  for (const file of videos) {
    const key = `${file.name}-${file.size}`;
    if (existingKey.has(key)) continue;

    const url = URL.createObjectURL(file);
    const id = crypto.randomUUID();
    const item = { id, file, url, duration: undefined };
    state.items.push(item);
    renderItem(item);
    probeDuration(item);
  }

  updateCount();
  els.fileInput.value = "";
});

function probeDuration(item) {
  const v = document.createElement("video");
  v.preload = "metadata";
  v.muted = true;
  v.src = item.url;

  v.addEventListener("loadedmetadata", () => {
    item.duration = v.duration;
    const row = document.querySelector(`[data-id="${item.id}"]`);
    if (row) {
      const info = row.querySelector(".video-info");
      if (info) info.textContent = `${formatTime(item.duration)} • ${formatBytes(item.file.size)}`;
    }
    v.removeAttribute("src");
    v.load();
  }, { once: true });

  v.addEventListener("error", () => {
    const row = document.querySelector(`[data-id="${item.id}"]`);
    if (row) {
      const info = row.querySelector(".video-info");
      if (info) info.textContent = `${formatBytes(item.file.size)}`;
    }
  }, { once: true });
}

function renderItem(item) {
  const tbody = document.getElementById("videoListBody");

  const tr = document.createElement("tr");
  tr.dataset.id = item.id;

  //썸네일 준비
  const thumbTd = document.createElement("td");
  const img = document.createElement("img");
  img.className = "video-thumb-small";
  thumbTd.appendChild(img);

  //썸네일 생성되면 넣어줌
  generateThumbnail(item.file, item.url, (dataURL) => {
    img.src = dataURL;
  });

  //점수 5개 열
  const fields = ["sexuality","violence","horror","drugs","language"];
  const scoreTds = {};

  fields.forEach(key => {
    const td = document.createElement("td");
    td.textContent = "";
    scoreTds[key] = td;
    tr.appendChild(td);
  });

  //삭제 버튼
  const delTd = document.createElement("td");
  const delBtn = document.createElement("button");
  delBtn.className = "delete-btn";
  delBtn.innerHTML = "🗑️";

  delBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    state.items = state.items.filter(v => v.id !== item.id);
    tr.remove();
    updateCount();
  });
  delTd.appendChild(delBtn);

  tr.appendChild(thumbTd);
  fields.forEach(k => tr.appendChild(scoreTds[k]));
  tr.appendChild(delTd);

  //항목 클릭하면 재생 및 분석
  tr.addEventListener("click", () => {
    els.player.src = item.url;
    els.player.style.display = "block";
    els.player.play().catch(err => {
      console.error("Play error:", err);
    });

    document.getElementById("videoTitle").textContent = item.file.name;
    document.getElementById("videoDesc").textContent = "";

    analyzeVideo(item.file);
  });

  tbody.appendChild(tr);

  //테이블용 점수 셀들을 item에 저장
  item.scoreCells = scoreTds;
}

//캐시 생성
function buildCacheKey(file) {
  return [
    file.name,
    file.size,
    file.lastModified
  ].join("|");
}

/*영상 전송 및 분석*/
async function analyzeVideo(file) {
  const filename = file.name;
  const cacheKey = buildCacheKey(file);

  // Store current filename for feedback submission
  state.currentFilename = filename;

  const descEl = document.getElementById("videoDesc");
  descEl.textContent = "🔍 분석 중…";

  // Clear result table while waiting for analysis
  clearResultTable();

  //프론트 캐시 먼저 확인
  if (summaryCache.has(cacheKey)) {
    const data = summaryCache.get(cacheKey);
    descEl.textContent = data.content_summary || "(설명 없음)";
    fillResultTable(data);

    // Update table scores
    const item = state.items.find(i => i.file.name === file.name && i.file.size === file.size);
    if (item) {
      applyScoresToList(item, data);
    }
    return;
  }

  //서버 캐시 확인
  let cached = await fetch(`/api/results/${encodeURIComponent(filename)}`);
  if (cached.ok) {
    const data = await cached.json();
    summaryCache.set(cacheKey, data);
    descEl.textContent = data.content_summary || "(설명 없음)";
    fillResultTable(data);

    // Update table scores
    const item = state.items.find(i => i.file.name === file.name && i.file.size === file.size);
    if (item) {
      applyScoresToList(item, data);
    }
    return;
  }

  //서버에 새로운 분석 요청 (NEW O/X system)
  const form = new FormData();
  form.append("video", file, filename);

  const res = await fetch("/api/analyze/ox", {
    method: "POST",
    body: form
  });

  const data = await res.json();

  //프론트 캐시에 저장
  summaryCache.set(cacheKey, data);

  descEl.textContent = data.content_summary || "(설명 없음)";
  fillResultTable(data);

  const item = state.items.find(i => i.file.name === file.name && i.file.size === file.size);
  if (item) {
    applyScoresToList(item, data);
  }
}

function applyScoresToList(item, data) {
  if (!item.scoreCells) return;

  // Use ox field instead of scores, and convert to O/X
  const oxData = data.ox || data.scores; // Fallback for compatibility
  Object.entries(oxData).forEach(([key, val]) => {
    if (item.scoreCells[key]) {
      item.scoreCells[key].textContent = toOX(val);
    }
  });
}

// 공통: 변경점 표시용 빨간 점 추가
function addChangedDotToCell(td) {
  if (!td) return;
  if (td.style.position !== "relative") {
    td.style.position = "relative";
  }
  if (td.querySelector(".ox-changed-dot")) return;

  const dot = document.createElement("span");
  dot.className = "ox-changed-dot";
  dot.style.position = "absolute";
  dot.style.top = "10px";
  dot.style.right = "10px";
  dot.style.width = "6px";
  dot.style.height = "6px";
  dot.style.background = "#e00";
  dot.style.borderRadius = "50%";
  dot.style.pointerEvents = "none";
  td.appendChild(dot);
}

// 변경된 O/X 표시 (오른쪽 위 작은 빨간 점)
function markChangedOx(item, changedKeys) {
  if (!item?.scoreCells || !Array.isArray(changedKeys) || changedKeys.length === 0) return;

  changedKeys.forEach((key) => {
    const td = item.scoreCells[key];
    if (!td) return;

    addChangedDotToCell(td);
  });
}

/* 평가결과 테이블 초기화 */
function clearResultTable() {
  const table = document.getElementById("resultTable");
  const rows = table.querySelectorAll("tbody tr");

  rows.forEach(row => {
    row.children[1].textContent = ""; // O/X column
    row.children[2].textContent = ""; // 근거 column
    row.children[3].innerHTML = "";   // 피드백 column
  });
}

/* 각 표 점수 채우기 */
function fillResultTable(data) {
  const scoreKeys = [
    "sexuality",
    "violence",
    "horror",
    "drugs",
    "language"
  ];

  const table = document.getElementById("resultTable");
  const rows = table.querySelectorAll("tbody tr");

  // Use ox field instead of scores, with fallback for compatibility
  const oxData = data.ox || data.scores;

  // 현재 선택된 파일의 변경 키
  const changedKeys = Array.isArray(state.oxChanges?.[state.currentFilename])
    ? state.oxChanges[state.currentFilename]
    : [];

  scoreKeys.forEach((key, index) => {
    const row = rows[index];

    // Display O/X instead of 0/1
    const oxValue = oxData[key];
    const oxTd = row.children[1];
    oxTd.textContent = oxValue !== undefined ? toOX(oxValue) : "";
    row.children[2].textContent = data.details[key] ?? "";

    // 기존 dot 제거 후 필요 시 dot 추가
    const prevDot = oxTd.querySelector(".ox-changed-dot");
    if (prevDot) prevDot.remove();
    if (changedKeys.includes(key)) {
      addChangedDotToCell(oxTd);
    }

    //피드백 버튼
    const feedbackTd = row.children[3];
    feedbackTd.innerHTML = "";

    const btn = document.createElement("button");
    btn.textContent = "작성하기";
    btn.className = "btn mini";
    btn.style.padding = "4px 8px";
    btn.style.fontSize = "11px";

    btn.addEventListener("click", () => {
      openFeedbackEditor(btn, key);
    });

    feedbackTd.appendChild(btn);
  });
}


function updateCount() {
  els.videoCount.textContent = `${state.items.length}개`;
}

window.addEventListener("beforeunload", () => {
  state.items.forEach(i => URL.revokeObjectURL(i.url));
});


//1초 기준으로 썸네일 생성
function generateThumbnail(file, url, callback) {
  const video = document.createElement("video");
  video.src = url;
  video.muted = true;
  video.preload = "auto";

  video.addEventListener("loadedmetadata", () => {
    const targetTime = video.duration > 1 ? 1 : 0.1;
    video.currentTime = targetTime;
  });

  video.addEventListener("seeked", () => {
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 90;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataURL = canvas.toDataURL("image/jpeg", 0.8);
    callback(dataURL);
  }, { once: true });
}

/* 피드백 상호작용 버튼 */
let activeEditor = null;

function openFeedbackEditor(button, categoryKey) {
  if (activeEditor) {
    activeEditor.remove();
    activeEditor = null;
  }

  const editor = document.createElement("div");
  editor.className = "feedback-editor";

  editor.innerHTML = `
    <textarea placeholder="피드백을 입력하세요"></textarea>
    <div class="actions">
      <button class="confirm">확인</button>
      <button class="cancel">취소</button>
    </div>
  `;

  document.body.appendChild(editor);

  //기본 위치 버튼 바로 아래
  const rect = button.getBoundingClientRect();
  let x = rect.left + window.scrollX;
  let y = rect.bottom + window.scrollY;

  //에디터 크기 계산
  const editorWidth = editor.offsetWidth;
  const editorHeight = editor.offsetHeight;

  const screenWidth = window.innerWidth;
  const screenHeight = window.innerHeight;

  //오른쪽 넘치면 왼쪽으로 이동
  if (x + editorWidth > screenWidth - 10) {
    x = screenWidth - editorWidth - 10;
  }

  //아래 넘치면 위로 이동
  if (y + editorHeight > screenHeight - 10) {
    y = rect.top + window.scrollY - editorHeight - 10;
  }

  //완전히 화면 밖으로 못나가게 최소값 지정
  if (x < 10) x = 10;
  if (y < 10) y = 10;

  editor.style.left = x + "px";
  editor.style.top = y + "px";

  activeEditor = editor;

  // 버튼 기능
  const textarea = editor.querySelector("textarea");
  const confirmBtn = editor.querySelector(".confirm");
  const cancelBtn = editor.querySelector(".cancel");

  confirmBtn.addEventListener("click", async () => {
    const text = textarea.value.trim();
    if (!text) return;

    if (!state.currentFilename) {
      alert("영상을 먼저 선택해주세요.");
      return;
    }

    // Disable button during submission
    confirmBtn.disabled = true;
    confirmBtn.textContent = "전송 중...";

    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          filename: state.currentFilename,
          criteria: categoryKey,
          feedback: text
        })
      });

      const result = await response.json();

      if (response.ok) {
        alert("✅ " + result.message);
        editor.remove();
        activeEditor = null;
      } else {
        alert("❌ 오류: " + (result.message || "피드백 저장 실패"));
        confirmBtn.disabled = false;
        confirmBtn.textContent = "확인";
      }
    } catch (error) {
      console.error("Feedback submission error:", error);
      alert("❌ 네트워크 오류가 발생했습니다.");
      confirmBtn.disabled = false;
      confirmBtn.textContent = "확인";
    }
  });

  cancelBtn.addEventListener("click", () => {
    editor.remove();
    activeEditor = null;
  });
}

/* 피드백 반영 버튼 */
const reanalyzeBtn = document.getElementById("reanalyzeBtn");

if (reanalyzeBtn) {
  reanalyzeBtn.addEventListener("click", async () => {
    if (!confirm("누적된 피드백을 반영하여 재심의를 진행하시겠습니까?\n시간이 다소 걸릴 수 있습니다.")) {
      return;
    }

    // Disable button and show loading state
    reanalyzeBtn.disabled = true;
    reanalyzeBtn.textContent = "재심의 중...";

    try {
      const response = await fetch("/api/reanalyze", {
        method: "POST"
      });

      const result = await response.json();

      if (response.ok) {
        alert("✅ " + result.message);

        // Show what changed
        // let changeMsg = "\n변경된 항목:\n";
        // for (const [filename, changedCriteria] of Object.entries(result.changes)) {
        //   if (changedCriteria.length > 0) {
        //     changeMsg += `\n📹 ${filename}\n`;
        //     changedCriteria.forEach(c => {
        //       changeMsg += `  - ${c}\n`;
        //     });
        //   }
        // }
        // alert(changeMsg);


        // Reload the page to show updated results
        location.reload();
      } else {
        // Debug logs (강화)
        try {
          console.groupCollapsed("[Reanalyze] 실패 상세 로그");
          console.error("서버가 OK가 아닌 상태코드로 응답");
          console.log("status:", response.status, response.statusText);
          console.log("url:", response.url);
          console.log("ok:", response.ok, "redirected:", response.redirected, "type:", response.type);
          try {
            console.log("headers:", Array.from(response.headers.entries()));
          } catch (e) {
            console.warn("헤더 로깅 중 오류:", e);
          }
          console.log("parsed result:", result);
          console.log("result.message:", result?.message);
          console.log("result.errors:", result?.errors);
          console.log("result.changes:", result?.changes);
          console.log("UI 상태 - 버튼 disabled:", reanalyzeBtn.disabled, "text:", reanalyzeBtn.textContent);
          console.log("현재 파일명(state.currentFilename):", state.currentFilename);
          // 전역 스냅샷 저장 (필요 시 콘솔에서 확인 가능)
          window.__reanalyzeLastError = {
            at: new Date().toISOString(),
            responseMeta: {
              status: response.status,
              statusText: response.statusText,
              url: response.url,
              ok: response.ok,
              redirected: response.redirected,
              type: response.type,
              headers: (() => {
                try { return Array.from(response.headers.entries()); } catch { return null; }
              })()
            },
            result
          };
          console.groupEnd();
        } catch (logError) {
          console.error("재심의 실패 로깅 중 오류:", logError);
        }
        alert("❌ 오류: " + (result?.message || `재심의 실패 (status ${response.status})`));
      }
    } catch (error) {
      console.error("Re-analyze error:", error);
      alert("❌ 네트워크 오류가 발생했습니다.");
    } finally {
      reanalyzeBtn.disabled = false;
      reanalyzeBtn.textContent = "피드백 반영";
    }
  });
}

// Clear result table on page load
clearResultTable();

// 초기 데이터 로드: 서버의 분석 결과와 실제 존재하는 영상 목록을 교집합으로 렌더링
window.addEventListener("DOMContentLoaded", async () => {
  try {
    // 동시 요청: 사용 가능한 파일 목록과 분석 결과
    const [videosRes, resultsRes, changesRes, consRes] = await Promise.all([
      fetch("/api/videos"),
      fetch("/api/results"),
      fetch("/api/changes"),
      fetch("/api/considerations")
    ]);

    if (!videosRes.ok || !resultsRes.ok) {
      return;
    }

    const [videos, results] = await Promise.all([videosRes.json(), resultsRes.json()]);

    // 변경된 O/X 정보 로드 (실패해도 무시)
    try {
      state.oxChanges = changesRes.ok ? await changesRes.json() : {};
    } catch {
      state.oxChanges = {};
    }

    // 평가 기준 설명 로드 및 툴팁 적용 (실패해도 무시)
    let considerations = {};
    try {
      considerations = consRes.ok ? await consRes.json() : {};
    } catch {
      considerations = {};
    }
    try {
      const labelToKey = {
        "선정성": "sexuality",
        "폭력성": "violence",
        "공포": "horror",
        "약물": "drugs",
        "언어": "language"
      };
      const rows = document.querySelectorAll("#resultTable tbody tr");
      rows.forEach((row) => {
        const nameCell = row.children?.[0];
        if (!nameCell) return;
        const key = labelToKey[(nameCell.textContent || "").trim()];
        const text = key ? considerations?.[key] : null;
        if (text) {
          nameCell.setAttribute("title", text);
        }
      });
    } catch {}

    // filename -> path 매핑
    const availableMap = new Map();
    (videos || []).forEach(v => {
      if (v && v.filename && v.path) availableMap.set(v.filename, v.path);
    });

    // 리스트 렌더링: 실제 있는 파일 중 분석 결과가 있는 것만
    const filenames = (videos || []).map(v => v.filename).filter(name => !!results[name]);

    filenames.forEach(filename => {
      const id = crypto.randomUUID();
      const url = availableMap.get(filename); // e.g. /api/videos/<filename>

      const item = {
        id,
        file: { name: filename, size: 0, lastModified: 0 },
        url,
        duration: undefined
      };

      state.items.push(item);
      renderItem(item);

      // 캐시에 저장(초기 클릭 시 서버 캐시 조회 생략 가능)
      const data = results[filename];
      const cacheKey = buildCacheKey(item.file);
      summaryCache.set(cacheKey, data);

      // 리스트 O/X 반영
      applyScoresToList(item, data);

      // 변경된 항목 표시
      const changedKeys = state.oxChanges?.[filename] || [];
      if (Array.isArray(changedKeys) && changedKeys.length > 0) {
        markChangedOx(item, changedKeys);
      }
    });

    updateCount();

    // 첫 항목 자동 선택: 상세 표시 및 플레이어 준비
    if (state.items.length > 0) {
      const first = state.items[0];
      state.currentFilename = first.file.name;
      els.player.src = first.url;
      els.player.style.display = "block";

      const firstData = summaryCache.get(buildCacheKey(first.file));
      document.getElementById("videoTitle").textContent = first.file.name;
      document.getElementById("videoDesc").textContent = firstData?.content_summary || "";
      if (firstData) fillResultTable(firstData);
    }
  } catch (err) {
    console.error("Initial load failed:", err);
  }
});