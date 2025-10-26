(function () {
  // Video preview wiring
  var fileInput = document.getElementById('video-file');
  var video = document.getElementById('video-player');
  var summaryCache = new Map();
  if (fileInput && video) {
    fileInput.addEventListener('change', function (e) {
      var file = e.target.files && e.target.files[0];
      if (!file) return;
      var url = URL.createObjectURL(file);
      video.src = url;
      video.load();
      video.play().catch(function () { /* autoplay may be blocked; ignore */ });
      summaryCache.clear();
    });
  }

  const output = document.getElementById('output-content');
  const requirementsInput = document.getElementById('requirements-input');

  function buildSummaryKey(file, requirements) {
    var name = file && file.name ? file.name : '';
    var size = file && typeof file.size === 'number' ? String(file.size) : '';
    var mtime = file && typeof file.lastModified === 'number' ? String(file.lastModified) : '';
    return ['v1', name, size, mtime, requirements].join('|');
  }

  async function analyzeSummaryViaApi() {
    const fileEl = document.getElementById('video-file');
    const file = fileEl && fileEl.files && fileEl.files[0];
    if (!file) {
      output.textContent = '비디오 파일을 먼저 선택하세요.';
      return;
    }

    const requirements = (requirementsInput && requirementsInput.value || '').trim();
    const cacheKey = buildSummaryKey(file, requirements);
    if (summaryCache.has(cacheKey)) {
      output.textContent = summaryCache.get(cacheKey);
      return;
    }
    const form = new FormData();
    form.append('video', file, file.name || 'video.mp4');
    form.append('requirements', requirements);

    output.textContent = '분석 중... 잠시만 기다려주세요.';
    try {
      const apiOrigin = (window.location && window.location.port === '5000')
        ? ''
        : 'http://127.0.0.1:5000';
      const res = await fetch(apiOrigin + '/api/analyze/summary', {
        method: 'POST',
        body: form
      });
      const ct = res.headers.get('content-type') || '';
      if (!res.ok) {
        let msg = '분석 실패';
        if (ct.includes('application/json')) {
          const j = await res.json();
          msg = (j && (j.message || j.error)) || msg;
        } else {
          msg = await res.text();
        }
        output.textContent = msg;
        return;
      }
      const text = await res.text();
      output.textContent = text || '결과를 표시할 수 없습니다.';
      summaryCache.set(cacheKey, output.textContent);
    } catch (err) {
      output.textContent = '오류가 발생했습니다: ' + (err && err.message ? err.message : String(err));
    }
  }

  // Placeholder responses per category; integrate real AI later
  const responses = {
    summary: '요약:\n- 각 카테고리의 핵심 판단 근거를 간단히 모아 제공합니다.',
    topic: '주제 분석 결과:\n- 영상의 주요 주제와 메시지를 간단히 요약합니다.',
    sexuality: '선정성 분석 결과:\n- 노출, 성적 표현, 연령 적합성 등의 요소를 요약합니다.',
    violence: '폭력성 분석 결과:\n- 폭력 장면의 빈도, 강도, 피해자/가해자 표현을 요약합니다.',
    dialogue: '대사 분석 결과:\n- 비속어, 혐오표현, 모욕적 표현의 존재 여부를 요약합니다.',
    horror: '공포 요소 분석 결과:\n- 공포 연출 강도, 놀람 유도 장면, 잔혹성 등을 요약합니다.',
    drugs: '약물 요소 분석 결과:\n- 약물 사용/미화/권장 여부와 맥락을 요약합니다.',
    imitable: '모방위험 분석 결과:\n- 위험행동의 묘사, 접근성, 안전장치 설명 여부를 요약합니다.'
  };

  function handleClick(event) {
    const key = event.currentTarget.getAttribute('data-key');
    if (key === 'summary') {
      analyzeSummaryViaApi();
      return;
    }
    const text = responses[key] || '선택한 항목에 대한 결과가 없습니다.';
    output.textContent = text;
  }

  const buttons = document.querySelectorAll('.category');
  buttons.forEach(function (btn) {
    btn.addEventListener('click', handleClick);
  });
})();


