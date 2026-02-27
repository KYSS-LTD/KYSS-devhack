const pin = window.QUIZBATTLE_PIN;
const playerRaw = localStorage.getItem('qb_player');
if (!playerRaw) window.location.href = '/';
const player = playerRaw ? JSON.parse(playerRaw) : null;
const hasValidPlayer = Boolean(player && player.pin === pin && player.player_token);
if (!hasValidPlayer) {
  localStorage.removeItem('qb_player');
  window.location.replace('/');
}

const topicEl = document.getElementById('topic');
const scoreA = document.getElementById('score-a');
const scoreB = document.getElementById('score-b');
const turnEl = document.getElementById('turn');
const teamSection = document.getElementById('team-section');
const lobbySection = document.getElementById('lobby-section');
const lobbyList = document.getElementById('lobby-list');
const teamAList = document.getElementById('team-a-list');
const teamBList = document.getElementById('team-b-list');
const qTitle = document.getElementById('question-title');
const qText = document.getElementById('question-text');
const answersEl = document.getElementById('answers');
const resultEl = document.getElementById('answer-result');
const timerEl = document.getElementById('timer');
const voteStatsEl = document.getElementById('vote-stats');
const startBtn = document.getElementById('start-btn');
const saveResultsBtn = document.getElementById('save-results-btn');
const captainControlsEl = document.getElementById('captain-controls');
const captainSelectEl = document.getElementById('captain-select');
const transferCaptainBtn = document.getElementById('transfer-captain-btn');
const hostControlsEl = document.getElementById('host-controls');
const pauseBtn = document.getElementById('pause-btn');
const resumeBtn = document.getElementById('resume-btn');
const nextQuestionBtn = document.getElementById('next-question-btn');
const kickPlayerSelectEl = document.getElementById('kick-player-select');
const kickBtn = document.getElementById('kick-btn');
const restartControlsEl = document.getElementById('restart-controls');
const restartTopicEl = document.getElementById('restart-topic');
const restartDifficultyEl = document.getElementById('restart-difficulty');
const restartBtn = document.getElementById('restart-btn');

let ws;
let currentQuestionId = null;
let localTimer = null;
let leftSeconds = 30;
let latestState = null;
let restartPending = false;
let previousPhase = null;

function wsUrl(path) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}${path}`;
}

function sendHostControl(controlAction, targetPlayerId = null) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({
    action: 'host_control',
    control_action: controlAction,
    target_player_id: targetPlayerId,
  }));
}

function startCountdown(seconds) {
  clearInterval(localTimer);
  leftSeconds = seconds;
  timerEl.textContent = `До старта: ${leftSeconds}`;
  localTimer = setInterval(() => {
    leftSeconds -= 1;
    timerEl.textContent = leftSeconds > 0 ? `До старта: ${leftSeconds}` : 'Старт!';
    if (leftSeconds <= 0) clearInterval(localTimer);
  }, 1000);
}

function startQuestionTimer(seconds = 30) {
  clearInterval(localTimer);
  leftSeconds = Math.max(0, Number(seconds) || 30);
  timerEl.textContent = leftSeconds > 0 ? `Осталось: ${leftSeconds} сек` : 'Время вышло';
  localTimer = setInterval(() => {
    leftSeconds -= 1;
    timerEl.textContent = leftSeconds > 0 ? `Осталось: ${leftSeconds} сек` : 'Время вышло';
    if (leftSeconds <= 0) clearInterval(localTimer);
  }, 1000);
}

function renderLobby(players) {
  lobbyList.innerHTML = '';
  players.forEach((p) => {
    const li = document.createElement('li');
    li.className = 'flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-700/50 last:border-0';

    const left = document.createElement('span');
    left.textContent = p.name;

    if (p.is_host) {
      const hostBadge = document.createElement('span');
      hostBadge.className = 'text-[10px] bg-indigo-100 dark:bg-indigo-900 text-indigo-500 px-1.5 py-0.5 rounded ml-1';
      hostBadge.textContent = 'HOST';
      left.appendChild(hostBadge);
    }

    const right = document.createElement('span');
    right.className = 'w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]';

    li.appendChild(left);
    li.appendChild(right);
    lobbyList.appendChild(li);
  });
}

function renderTeams(players, me, allowCaptainControls) {
  teamAList.innerHTML = '';
  teamBList.innerHTML = '';

  const myTeam = me ? me.team : null;
  const isCaptain = Boolean(me && me.is_captain && myTeam);
  const candidates = [];

  players.forEach((p) => {
    const li = document.createElement('li');
    const crown = p.is_captain ? ' 👑' : '';
    li.textContent = `${p.name}${p.is_host ? ' (ведущий)' : ''}${crown}`;
    if (p.team === 'A') {
      li.className = 'team-a';
      teamAList.appendChild(li);
    } else if (p.team === 'B') {
      li.className = 'team-b';
      teamBList.appendChild(li);
    }

    if (isCaptain && p.team === myTeam && p.id !== me.id && !p.is_captain) {
      candidates.push(p);
    }
  });

  captainSelectEl.innerHTML = '';
  if (allowCaptainControls && isCaptain && candidates.length > 0) {
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Выберите игрока';
    captainSelectEl.appendChild(placeholder);

    candidates.forEach((candidate) => {
      const option = document.createElement('option');
      option.value = String(candidate.id);
      option.textContent = candidate.name;
      captainSelectEl.appendChild(option);
    });

    captainControlsEl.classList.remove('hidden');
  } else {
    captainControlsEl.classList.add('hidden');
  }
}

function renderHostControls(players, me, state) {
  if (!me || !me.is_host || state.status !== 'in_progress') {
    hostControlsEl.classList.add('hidden');
    return;
  }

  hostControlsEl.classList.remove('hidden');
  pauseBtn.disabled = state.phase === 'paused';
  resumeBtn.disabled = state.phase !== 'paused';
  nextQuestionBtn.disabled = state.phase !== 'question';

  const candidates = players.filter((p) => p.id !== me.id);
  kickPlayerSelectEl.innerHTML = '';
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = candidates.length > 0 ? 'Выберите игрока' : 'Нет игроков для кика';
  kickPlayerSelectEl.appendChild(placeholder);

  candidates.forEach((candidate) => {
    const option = document.createElement('option');
    option.value = String(candidate.id);
    option.textContent = `${candidate.name}${candidate.team ? ` (${candidate.team === 'A' ? 'красная' : 'синяя'})` : ''}`;
    kickPlayerSelectEl.appendChild(option);
  });

  kickBtn.disabled = candidates.length === 0;
}

function votePercent(votePercentages, choice) {
  const value = votePercentages && votePercentages[choice];
  if (!value) return 0;
  return Number(value) || 0;
}

function handleAnswerClick(optionIndex, canAnswer, canVote) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  if (canAnswer) {
    ws.send(JSON.stringify({ action: 'answer', option_index: optionIndex }));
    return;
  }
  if (canVote) {
    ws.send(JSON.stringify({ action: 'vote', choice: String(optionIndex) }));
  }
}

function handleSkipClick(canAnswer, canVote) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  if (canAnswer) {
    ws.send(JSON.stringify({ action: 'skip' }));
    return;
  }
  if (canVote) {
    ws.send(JSON.stringify({ action: 'vote', choice: 'skip' }));
  }
}

function appendVoteBar(parent, percent) {
  if (!percent) return;
  const bar = document.createElement('div');
  bar.className = 'mb-1 px-3 py-1 rounded-t-lg bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-200 text-xs font-semibold';
  bar.textContent = `${percent}% — проголосовало`;
  parent.appendChild(bar);
}

function renderAnswers(options, canAnswer, canVote, votePercentages) {
  answersEl.innerHTML = '';

  options.forEach((option, idx) => {
    const choice = String(idx + 1);
    const percent = votePercent(votePercentages, choice);

    const wrap = document.createElement('div');
    wrap.className = 'mb-2';

    appendVoteBar(wrap, percent);

    const answerBtn = document.createElement('button');
    answerBtn.className = `w-full py-3 px-4 rounded-lg text-sm font-medium text-left transition ${canVote ? 'bg-indigo-600 text-white hover:bg-indigo-500 active:scale-[0.98]' : 'bg-slate-200 dark:bg-slate-700 text-slate-400 cursor-not-allowed'}`;
    answerBtn.textContent = `${idx + 1}. ${option}`;
    answerBtn.disabled = !canVote;
    answerBtn.onclick = () => handleAnswerClick(idx + 1, canAnswer, canVote);

    wrap.appendChild(answerBtn);
    answersEl.appendChild(wrap);
  });

  const skipPercent = votePercent(votePercentages, 'skip');
  const skipWrap = document.createElement('div');
  skipWrap.className = 'mt-4';
  appendVoteBar(skipWrap, skipPercent);

  const skipBtn = document.createElement('button');
  skipBtn.className = `w-full py-2 rounded-lg text-xs transition ${canVote ? 'border border-dashed border-slate-300 dark:border-slate-600 text-slate-500 dark:text-slate-300 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20' : 'bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed'}`;
  skipBtn.textContent = canAnswer ? 'Пропустить вопрос (капитан)' : 'Пропустить вопрос';
  skipBtn.disabled = !canVote;
  skipBtn.onclick = () => handleSkipClick(canAnswer, canVote);

  skipWrap.appendChild(skipBtn);
  answersEl.appendChild(skipWrap);
}

function renderVotes(votePercentages) {
  const entries = Object.entries(votePercentages || {});
  if (entries.length === 0) {
    voteStatsEl.textContent = '';
    return;
  }
  voteStatsEl.textContent = entries.map(([choice, pct]) => `${choice === 'skip' ? 'Пропуск' : `Вариант ${choice}`}: ${pct}%`).join(' | ');
}

function teamStatsText(stats) {
  return `Верно: ${stats.correct}, Неверно: ${stats.incorrect}, Таймаут: ${stats.timeout}, Бонус скорости: +${stats.speed_bonus}`;
}

function downloadResults(state) {
  const winner = state.winner === 'draw' ? 'Ничья' : state.winner === 'A' ? 'Красная команда' : 'Синяя команда';
  const rows = [
    '===========================================',
    '             QUIZBATTLE REPORT             ',
    '===========================================',
    `Комната: ${state.pin}`,
    `Тема: ${state.topic}`,
    `Сложность: ${state.difficulty}`,
    `Итоговый счёт: Красные ${state.score_a} : Синие ${state.score_b}`,
    `Победитель: ${winner}`,
    '',
    'Командная статистика:',
    `  Красные: ${teamStatsText(state.team_stats.A)}`,
    `  Синие: ${teamStatsText(state.team_stats.B)}`,
    '===========================================',
  ];
  const blob = new Blob([rows.join('\n')], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `quizbattle-result-${state.pin}.txt`;
  a.click();
}

function renderResultSummary(state) {
  const winner = state.winner === 'draw' ? 'Ничья' : state.winner === 'A' ? 'Красная команда' : 'Синяя команда';
  resultEl.innerHTML = [
    `<strong>Победитель:</strong> ${winner}`,
    `<strong>Итоговый счёт:</strong> Красные ${state.score_a} : Синие ${state.score_b}`,
    `<strong>Красные:</strong> ${teamStatsText(state.team_stats.A)}`,
    `<strong>Синие:</strong> ${teamStatsText(state.team_stats.B)}`,
  ].join('<br>');
}

function renderState(state) {
  const prevPhase = previousPhase;
  previousPhase = state.phase;
  latestState = state;
  topicEl.textContent = `Тема: ${state.topic} (${state.difficulty})`;
  scoreA.textContent = state.score_a;
  scoreB.textContent = state.score_b;
  const me = state.players.find((p) => p.id === player.player_id);

  renderLobby(state.players);
  const isGameplay = state.status === 'in_progress';
  renderTeams(state.players, me, isGameplay);
  renderHostControls(state.players, me, state);
  renderVotes(state.vote_percentages);

  const teamName = state.current_team === 'A' ? 'красная' : 'синяя';

  if (state.status === 'waiting') {
    lobbySection.classList.remove('hidden');
    teamSection.classList.add('hidden');
    captainControlsEl.classList.add('hidden');
    hostControlsEl.classList.add('hidden');
    turnEl.textContent = 'Период подключения: участники в лобби';
    qText.textContent = `Здесь появится вопрос после начала игры`;
    answersEl.innerHTML = '';
    timerEl.textContent = '';
    currentQuestionId = null;
    clearInterval(localTimer);
    localTimer = null;
    saveResultsBtn.classList.add('hidden');
    restartControlsEl.classList.add('hidden');
    if (me && me.is_host) {
      startBtn.classList.remove('hidden');
      startBtn.disabled = false;
      if (restartPending) {
        resultEl.textContent = 'Новый матч готов. Нажмите «Начать игру».';
      }
    } else {
      startBtn.classList.add('hidden');
      resultEl.textContent = '';
    }
    restartPending = false;
  } else if (state.phase === 'countdown') {
    lobbySection.classList.add('hidden');
    teamSection.classList.remove('hidden');
    captainControlsEl.classList.add('hidden');
    hostControlsEl.classList.add('hidden');
    restartPending = false;
    saveResultsBtn.classList.add('hidden');
    restartControlsEl.classList.add('hidden');
    startBtn.classList.add('hidden');
    turnEl.textContent = 'Игра запускается...';
    qText.textContent = 'Приготовьтесь!';
    answersEl.innerHTML = '';
    startCountdown(state.countdown_seconds || 3);
  } else if (state.status === 'in_progress') {
    lobbySection.classList.add('hidden');
    teamSection.classList.remove('hidden');
    restartPending = false;
    saveResultsBtn.classList.add('hidden');
    restartControlsEl.classList.add('hidden');
    startBtn.classList.add('hidden');

    if (state.phase === 'paused') {
      turnEl.textContent = 'Игра на паузе';
      answersEl.innerHTML = '';
      clearInterval(localTimer);
      localTimer = null;
      timerEl.textContent = 'Пауза';
    } else {
      turnEl.textContent = `Сейчас отвечает ${teamName} команда`;
      if (state.current_question) {
        qTitle.textContent = `Раунд ${state.current_question.order_index + 1}`;
        qText.textContent = state.current_question.text;
        const canVote = me && me.team === state.current_team;
        const canAnswer = canVote && me.is_captain;
        renderAnswers(state.current_question.options, canAnswer, canVote, state.vote_percentages);
        if (currentQuestionId !== state.current_question.id) {
          currentQuestionId = state.current_question.id;
          resultEl.textContent = '';
          startQuestionTimer(state.question_seconds_left ?? 30);
        } else if ((prevPhase === 'paused' || !localTimer || leftSeconds <= 0) && state.question_seconds_left !== null && state.question_seconds_left !== undefined) {
          startQuestionTimer(state.question_seconds_left);
        }
      }
    }
  } else {
    lobbySection.classList.add('hidden');
    teamSection.classList.remove('hidden');
    captainControlsEl.classList.add('hidden');
    hostControlsEl.classList.add('hidden');
    turnEl.textContent = 'Игра завершена';
    clearInterval(localTimer);
    localTimer = null;
    timerEl.textContent = '';
    answersEl.innerHTML = '';
    saveResultsBtn.classList.remove('hidden');
    if (me && me.is_host) restartControlsEl.classList.remove('hidden');
    qText.textContent = 'Матч окончен.';
    renderResultSummary(state);
  }
}

startBtn.addEventListener('click', async () => {
  startBtn.disabled = true;
  try {
    const res = await fetch(`/games/${pin}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ host_player_id: player.player_id }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Не удалось стартовать');
  } catch (err) {
    resultEl.textContent = err.message;
    startBtn.disabled = false;
  }
});

saveResultsBtn.addEventListener('click', () => {
  if (latestState) downloadResults(latestState);
});

transferCaptainBtn.addEventListener('click', () => {
  const selected = captainSelectEl.value;
  if (!selected) {
    resultEl.textContent = 'Выберите игрока для передачи лидерства';
    return;
  }
  ws.send(JSON.stringify({ action: 'transfer_captain', to_player_id: Number(selected) }));
});

pauseBtn.addEventListener('click', () => sendHostControl('pause'));
resumeBtn.addEventListener('click', () => sendHostControl('resume'));
nextQuestionBtn.addEventListener('click', () => sendHostControl('next_question'));
kickBtn.addEventListener('click', () => {
  const selected = kickPlayerSelectEl.value;
  if (!selected) {
    resultEl.textContent = 'Выберите игрока для кика';
    return;
  }
  sendHostControl('kick', Number(selected));
});

restartBtn.addEventListener('click', () => {
  if (!restartTopicEl.value.trim()) {
    resultEl.textContent = 'Введите новую тему для следующей игры';
    return;
  }
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    resultEl.textContent = 'Соединение нестабильно, попробуйте ещё раз через секунду';
    return;
  }
  restartPending = true;
  restartBtn.disabled = true;
  ws.send(JSON.stringify({
    action: 'host_control',
    control_action: 'restart',
    topic: restartTopicEl.value.trim(),
    difficulty: restartDifficultyEl.value,
  }));
  restartControlsEl.classList.add('hidden');
  resultEl.textContent = 'Запускаем новый матч...';
});

function connect() {
  if (!hasValidPlayer) return;
  const wsToken = encodeURIComponent(player.player_token || '');
  ws = new WebSocket(wsUrl(`/ws/${pin}/${player.player_id}?token=${wsToken}`));
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state') {
      restartBtn.disabled = false;
      renderState(msg.data);
    }
    if (msg.type === 'answer_result') {
      if (msg.data.timeout) resultEl.textContent = 'Время вышло';
      else if (msg.data.skip) resultEl.textContent = 'Вопрос пропущен';
      else resultEl.textContent = msg.data.correct ? 'Верно!' : `Неверно. Правильный ответ: ${msg.data.correct_option}`;
    }
  };
  ws.onclose = () => {
    restartBtn.disabled = false;
    if (restartPending) resultEl.textContent = 'Соединение перезапущено, проверьте состояние комнаты';
    setTimeout(connect, 2000);
  };
}

connect();