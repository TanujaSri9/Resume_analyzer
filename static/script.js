/* =============================================================
   TIMESTAMP FORMATTING  (all pages)
   ============================================================= */
document.querySelectorAll('[data-ts]').forEach(el => {
    try {
        const d = new Date(el.dataset.ts);
        if (isNaN(d)) return;
        el.textContent =
            d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) +
            ' · ' +
            d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch (_) {}
});


/* =============================================================
   SCORE RING ANIMATION  (result page)
   ============================================================= */
const rings = document.querySelectorAll('.ring-fg[data-offset]');
if (rings.length) {
    requestAnimationFrame(() => {
        setTimeout(() => rings.forEach(r => (r.style.strokeDashoffset = r.dataset.offset)), 150);
    });
}


/* =============================================================
   MAIN TABS  (result page)
   ============================================================= */
const tabBtns   = document.querySelectorAll('.tab-btn[data-tab]');
const tabPanels = document.querySelectorAll('.tab-panel[id^="tab-"]');

if (tabBtns.length) {
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            tabPanels.forEach(p => (p.hidden = true));
            const target = document.getElementById('tab-' + btn.dataset.tab);
            if (target) target.hidden = false;
            document.querySelector('.tab-nav')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    });
}


/* =============================================================
   SUB-TABS  (HR vs Technical)
   ============================================================= */
const subtabBtns   = document.querySelectorAll('.subtab-btn[data-subtab]');
const subtabPanels = document.querySelectorAll('.subtab-panel[id^="subtab-"]');

if (subtabBtns.length) {
    subtabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            subtabBtns.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            subtabPanels.forEach(p => (p.hidden = true));
            const target = document.getElementById('subtab-' + btn.dataset.subtab);
            if (target) target.hidden = false;
        });
    });
}


/* =============================================================
   COPY TO CLIPBOARD  (cover letter page)
   ============================================================= */
const copyBtn    = document.getElementById('copy-btn');
const letterBody = document.getElementById('letter-body');

if (copyBtn && letterBody) {
    copyBtn.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(letterBody.textContent.trim());
            _flashCopy(copyBtn, '✓ Copied!');
        } catch (_) {
            const range = document.createRange();
            range.selectNodeContents(letterBody);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            document.execCommand('copy');
            _flashCopy(copyBtn, '✓ Copied!');
        }
    });
}


/* =============================================================
   COPY SCORE TEXT  (score sharing card)
   ============================================================= */
const copyShareBtn = document.getElementById('copy-share-btn');

if (copyShareBtn) {
    copyShareBtn.addEventListener('click', async () => {
        const card = document.getElementById('score-share-card');
        if (!card) return;
        const nums  = [...card.querySelectorAll('.share-score-num')].map(el => el.textContent.trim());
        const labels = [...card.querySelectorAll('.share-score-label')].map(el => el.textContent.trim());
        const role  = card.querySelector('.share-role-badge')?.textContent.trim() || '';
        const text  = `📊 My Resume Score — AI Resume Analyzer\n${role}\n\n${labels.map((l, i) => `${l}: ${nums[i]}`).join('  ·  ')}\n\nGet yours free at resumeai.app`;
        try {
            await navigator.clipboard.writeText(text);
            _flashCopy(copyShareBtn, '✓ Copied!');
        } catch (_) {}
    });
}


function _flashCopy(btn, msg) {
    const orig = btn.textContent;
    btn.textContent = msg;
    btn.style.borderColor = 'var(--green-b)';
    btn.style.color = 'var(--green)';
    btn.style.background = 'var(--green-d)';
    setTimeout(() => {
        btn.textContent = orig;
        btn.style.borderColor = '';
        btn.style.color = '';
        btn.style.background = '';
    }, 2500);
}


/* =============================================================
   PROFESSIONAL SUMMARY GENERATOR  (AJAX, result page)
   ============================================================= */
const genSummaryBtn  = document.getElementById('gen-summary-btn');
const summaryResultBox = document.getElementById('summary-result-box');

if (genSummaryBtn && summaryResultBox) {
    genSummaryBtn.addEventListener('click', async () => {
        const recordId = genSummaryBtn.dataset.recordId;
        if (!recordId) return;

        genSummaryBtn.disabled = true;
        genSummaryBtn.textContent = '⏳ Generating…';

        try {
            const res  = await fetch(`/history/${recordId}/summary`, { method: 'POST' });
            const data = await res.json();

            if (data.error) {
                summaryResultBox.textContent = '⚠ ' + data.error;
                summaryResultBox.style.display = 'block';
                summaryResultBox.style.background = 'var(--rose-d)';
                summaryResultBox.style.borderColor = 'var(--rose-b)';
                summaryResultBox.style.color = 'var(--rose)';
            } else {
                summaryResultBox.textContent = data.summary;
                summaryResultBox.style.display = 'block';
                summaryResultBox.style.background = '';
                summaryResultBox.style.borderColor = '';
                summaryResultBox.style.color = '';

                // add copy button below
                let copyEl = document.getElementById('copy-summary-btn');
                if (!copyEl) {
                    copyEl = document.createElement('button');
                    copyEl.id = 'copy-summary-btn';
                    copyEl.className = 'btn-copy';
                    copyEl.textContent = '📋 Copy Summary';
                    copyEl.style.marginTop = '10px';
                    summaryResultBox.after(copyEl);
                }
                copyEl.onclick = async () => {
                    try {
                        await navigator.clipboard.writeText(data.summary.trim());
                        _flashCopy(copyEl, '✓ Copied!');
                    } catch (_) {}
                };
            }
        } catch (err) {
            summaryResultBox.textContent = '⚠ Network error. Please try again.';
            summaryResultBox.style.display = 'block';
        } finally {
            genSummaryBtn.disabled = false;
            genSummaryBtn.textContent = '↻ Regenerate Summary';
        }
    });
}


/* =============================================================
   INDEX PAGE — file upload & loading overlay
   ============================================================= */
const form            = document.getElementById('analyze-form');
const analyzeBtn      = document.getElementById('analyze-btn');
const loadingOverlay  = document.getElementById('loading-overlay');
const loadingMsg      = document.getElementById('loading-msg');
const uploadBox       = document.getElementById('upload-box');
const fileInput       = document.getElementById('resume-input');
const filenameDisplay = document.getElementById('filename-display');

const LOADING_MSGS = [
    'Reading resume content…',
    'Comparing skills with selected role…',
    'Checking job description alignment…',
    'Generating HR interview questions…',
    'Building technical question bank…',
    'Mapping your skill gaps…',
    'Finding certification recommendations…',
    'Enhancing project descriptions…',
    'Almost done — compiling your report…',
];

function showFilename(name) {
    if (!filenameDisplay) return;
    filenameDisplay.textContent = '📎 ' + name;
    filenameDisplay.hidden = false;
    if (uploadBox) uploadBox.querySelector('.upload-title').textContent = 'Resume selected';
}

if (fileInput) {
    fileInput.addEventListener('change', () => {
        if (fileInput.files[0]) showFilename(fileInput.files[0].name);
    });
}

/* --- Drag-and-drop ------------------------------------------- */
if (uploadBox && fileInput) {
    ['dragenter', 'dragover'].forEach(ev =>
        uploadBox.addEventListener(ev, e => { e.preventDefault(); uploadBox.classList.add('drag-over'); })
    );
    ['dragleave', 'dragend'].forEach(ev =>
        uploadBox.addEventListener(ev, () => uploadBox.classList.remove('drag-over'))
    );
    uploadBox.addEventListener('drop', e => {
        e.preventDefault();
        uploadBox.classList.remove('drag-over');
        const file = e.dataTransfer?.files[0];
        if (!file || (!file.name.endsWith('.pdf') && !file.name.endsWith('.docx'))) return;
        try {
            const dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;
        } catch (_) {}
        showFilename(file.name);
    });
}

/* --- Form submit & loading overlay --------------------------- */
if (form && analyzeBtn && loadingOverlay && loadingMsg) {
    form.addEventListener('submit', () => {
        if (!form.checkValidity()) return;
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = 'Analyzing…';
        loadingOverlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('is-analyzing');

        let idx = 0;
        loadingMsg.textContent = LOADING_MSGS[0];
        const timer = setInterval(() => {
            idx = (idx + 1) % LOADING_MSGS.length;
            loadingMsg.textContent = LOADING_MSGS[idx];
        }, 2500);
        window.addEventListener('pagehide', () => clearInterval(timer), { once: true });
    });
}

/* --- Landing page smooth scroll CTA ------------------------- */
document.querySelectorAll('a[href="#analyze"]').forEach(a => {
    a.addEventListener('click', e => {
        const target = document.getElementById('analyze');
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});


/* =============================================================
   MOCK INTERVIEW SIMULATOR
   ============================================================= */
const startBtn     = document.getElementById('start-interview-btn');
const restartBtn   = document.getElementById('restart-btn');
const retryBtn     = document.getElementById('retry-btn');
const sendBtn      = document.getElementById('send-btn');
const userAnswerEl = document.getElementById('user-answer');
const chatMessages = document.getElementById('chat-messages');
const chatThinking = document.getElementById('chat-thinking');
const chatInputRow = document.getElementById('chat-input-row');
const chatStatus   = document.getElementById('chat-status');
const chatRoleLabel = document.getElementById('chat-role-label');
const interviewSetup   = document.getElementById('interview-setup');
const interviewChat    = document.getElementById('interview-chat');
const interviewSummary = document.getElementById('interview-summary');
const summaryBody      = document.getElementById('summary-body');

let mockMessages   = [];  // [{role, content}]
let questionNum    = 1;
let interviewRole  = '';
let isBusy         = false;

function resetInterview() {
    mockMessages  = [];
    questionNum   = 1;
    isBusy        = false;
    if (chatMessages) chatMessages.innerHTML = '';
    if (chatStatus) chatStatus.textContent = 'Question 1 of 5';
    if (sendBtn) sendBtn.disabled = false;
    if (chatInputRow) chatInputRow.hidden = false;
    if (chatThinking) chatThinking.hidden = true;
    if (interviewSummary) interviewSummary.hidden = true;
    if (interviewChat) interviewChat.hidden = true;
    if (interviewSetup) interviewSetup.hidden = false;
}

function appendMessage(role, text, type = 'ai') {
    if (!chatMessages) return;
    const isAI   = role === 'assistant';
    const isUser = role === 'user';

    const wrapper = document.createElement('div');
    wrapper.className = `chat-msg ${isAI ? 'chat-msg-ai' : 'chat-msg-user'}`;

    const avatar = document.createElement('div');
    avatar.className = `chat-msg-avatar ${isAI ? 'avatar-ai' : 'avatar-user'}`;
    avatar.textContent = isAI ? '🤖' : '🧑';

    const bubble = document.createElement('div');
    const bubbleClass = type === 'feedback' ? 'bubble-feedback' : (isAI ? 'bubble-ai' : 'bubble-user');
    bubble.className = `chat-msg-bubble ${bubbleClass}`;
    bubble.textContent = text;

    wrapper.append(avatar, bubble);
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function fetchInterviewResponse() {
    isBusy = true;
    if (sendBtn) sendBtn.disabled = true;
    if (chatThinking) chatThinking.hidden = false;
    if (chatInputRow) chatInputRow.hidden = true;

    try {
        const res = await fetch('/mock-interview/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                role: interviewRole,
                messages: mockMessages,
                question_num: questionNum,
            }),
        });

        const data = await res.json();

        if (data.error) {
            appendMessage('assistant', '⚠ ' + data.error, 'ai');
        } else {
            // Show feedback (not on first question)
            if (data.feedback && questionNum > 1) {
                appendMessage('assistant', '💬 ' + data.feedback, 'feedback');
            }

            if (data.is_final) {
                // Show summary
                if (chatThinking) chatThinking.hidden = true;
                if (chatInputRow) chatInputRow.hidden = true;
                if (interviewSummary) interviewSummary.hidden = false;
                if (summaryBody) summaryBody.textContent = data.summary || 'Interview complete. Great job!';
                if (chatStatus) chatStatus.textContent = '✓ Interview complete';
            } else {
                // Show next question
                appendMessage('assistant', `Q${questionNum}: ${data.question}`, 'ai');
                mockMessages.push({ role: 'assistant', content: data.question });
                questionNum++;
                if (chatStatus) chatStatus.textContent = `Question ${questionNum - 1} of 5`;
                if (chatThinking) chatThinking.hidden = true;
                if (chatInputRow) chatInputRow.hidden = false;
                if (sendBtn) sendBtn.disabled = false;
                if (userAnswerEl) userAnswerEl.focus();
            }
        }
    } catch (err) {
        appendMessage('assistant', '⚠ Network error. Please check your connection and try again.', 'ai');
        if (chatThinking) chatThinking.hidden = true;
        if (chatInputRow) chatInputRow.hidden = false;
        if (sendBtn) sendBtn.disabled = false;
    }

    isBusy = false;
}

async function submitAnswer() {
    if (isBusy || !userAnswerEl) return;
    const answer = userAnswerEl.value.trim();
    if (!answer) return;

    userAnswerEl.value = '';
    appendMessage('user', answer, 'user');
    mockMessages.push({ role: 'user', content: answer });

    await fetchInterviewResponse();
}

if (startBtn) {
    startBtn.addEventListener('click', async () => {
        const roleEl   = document.getElementById('mock-role');
        const ctxEl    = document.getElementById('mock-context');
        interviewRole  = roleEl?.value || 'General';
        const context  = ctxEl?.value?.trim() || '';

        if (chatRoleLabel) chatRoleLabel.textContent = `AI Interviewer — ${interviewRole}`;

        if (interviewSetup) interviewSetup.hidden = true;
        if (interviewChat) interviewChat.hidden = false;

        if (context) {
            mockMessages.push({ role: 'system', content: `Candidate background: ${context}` });
        }

        await fetchInterviewResponse();
    });
}

if (sendBtn) {
    sendBtn.addEventListener('click', submitAnswer);
}

if (userAnswerEl) {
    userAnswerEl.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitAnswer();
        }
    });
}

if (restartBtn) {
    restartBtn.addEventListener('click', resetInterview);
}

if (retryBtn) {
    retryBtn.addEventListener('click', resetInterview);
}
