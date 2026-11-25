/**
 * NexovAI Voice AI Virtual Receptionist - Application Client
 * Real-time WebSocket connection, Web Speech STT/TTS bridge, live dashboard updates.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const btnOpenCallModal = document.getElementById('btnOpenCallModal');
  const phoneModal = document.getElementById('phoneModal');
  const btnEndCall = document.getElementById('btnEndCall');
  const btnToggleMic = document.getElementById('btnToggleMic');
  const phoneCallStatus = document.getElementById('phoneCallStatus');
  const phoneCallTimer = document.getElementById('phoneCallTimer');
  const callerAvatar = document.getElementById('callerAvatar');
  const phoneTranscriptBox = document.getElementById('phoneTranscriptBox');
  const phoneTextInput = document.getElementById('phoneTextInput');
  const btnSendText = document.getElementById('btnSendText');
  const phoneConfirmationCard = document.getElementById('phoneConfirmationCard');
  const phoneConfDetails = document.getElementById('phoneConfDetails');
  const phoneQuickActions = document.getElementById('phoneQuickActions');

  const doctorsListContainer = document.getElementById('doctorsListContainer');
  const appointmentsTableBody = document.getElementById('appointmentsTableBody');
  const doctorSearchInput = document.getElementById('doctorSearchInput');
  const btnResetDb = document.getElementById('btnResetDb');

  const metricDoctorsCount = document.getElementById('metricDoctorsCount');
  const metricSlotsCount = document.getElementById('metricSlotsCount');
  const metricBookingsCount = document.getElementById('metricBookingsCount');
  const slotsCountBadge = document.getElementById('slotsCountBadge');
  const appCountBadge = document.getElementById('appCountBadge');

  // Application State
  let ws = null;
  let isCallActive = false;
  let callTimerInterval = null;
  let callSeconds = 0;
  let speechRecognizer = null;
  let isMicActive = true;
  let visualizer = null;
  let allDoctors = [];

  // Initialize Canvas Visualizer
  visualizer = new window.AudioWaveformVisualizer('audioVisualizer');

  // Load Initial Dashboard Data
  fetchDoctors();
  fetchAppointments();

  // ============================================================================
  // WebSocket Voice Call Session Management
  // ============================================================================

  function connectCallSession() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/call`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[WebSocket] Connected to Voice Assistant Engine');
      ws.send(jsonStr({ action: 'start_call' }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleServerEvent(msg);
      } catch (err) {
        console.error('[WebSocket] Error parsing event:', err);
      }
    };

    ws.onclose = () => {
      console.log('[WebSocket] Connection closed');
      if (isCallActive) {
        handleCallEnded();
      }
    };

    ws.onerror = (err) => {
      console.error('[WebSocket] Error:', err);
    };
  }

  function handleServerEvent(msg) {
    switch (msg.type) {
      case 'state_change':
        onStateChange(msg.state);
        break;

      case 'transcript':
        appendTranscript(msg.speaker, msg.text, msg.timestamp);
        break;

      case 'audio_chunk':
        playAudioBase64(msg.audio);
        break;

      case 'appointment_booked':
        onAppointmentBooked(msg.data);
        break;

      case 'appointment_cancelled':
        onAppointmentCancelled(msg.data);
        break;

      case 'availability_checked':
        showToast(`Checked slots: ${msg.data.count} available`, 'success');
        break;

      case 'database_reset':
        fetchDoctors();
        fetchAppointments();
        showToast('Database reset to initial demo state', 'success');
        break;

      default:
        console.log('[Server Event]', msg);
    }
  }

  function onStateChange(state) {
    console.log('[Call State Changed]:', state);

    if (state === 'connecting') {
      phoneCallStatus.textContent = 'Ringing...';
      callerAvatar.classList.add('pulse');
      window.telephonyAudio.startRinging();
    } else if (state === 'connected') {
      window.telephonyAudio.playConnectChime();
      phoneCallStatus.textContent = 'Connected (Listening)';
      phoneCallStatus.style.color = '#34d399';
      startCallTimer();
      visualizer.start();
      visualizer.setMode('listening');
      startSpeechRecognition();
    } else if (state === 'thinking') {
      phoneCallStatus.textContent = 'Processing request...';
      phoneCallStatus.style.color = '#38bdf8';
      visualizer.setMode('idle');
    } else if (state === 'speaking') {
      phoneCallStatus.textContent = 'Agent Speaking...';
      phoneCallStatus.style.color = '#38bdf8';
      visualizer.setMode('speaking');
    } else if (state === 'listening') {
      phoneCallStatus.textContent = 'Listening to you...';
      phoneCallStatus.style.color = '#34d399';
      visualizer.setMode('listening');
    } else if (state === 'ended') {
      handleCallEnded();
    }
  }

  function startCallTimer() {
    callSeconds = 0;
    phoneCallTimer.textContent = '00:00';
    if (callTimerInterval) clearInterval(callTimerInterval);
    callTimerInterval = setInterval(() => {
      callSeconds++;
      const m = String(Math.floor(callSeconds / 60)).padStart(2, '0');
      const s = String(callSeconds % 60).padStart(2, '0');
      phoneCallTimer.textContent = `${m}:${s}`;
    }, 1000);
  }

  function stopCallTimer() {
    if (callTimerInterval) {
      clearInterval(callTimerInterval);
      callTimerInterval = null;
    }
  }

  function handleCallEnded() {
    isCallActive = false;
    stopCallTimer();
    stopSpeechRecognition();
    window.telephonyAudio.playHangupSound();
    visualizer.stop();

    phoneCallStatus.textContent = 'Call Ended';
    phoneCallStatus.style.color = '#ef4444';
    callerAvatar.classList.remove('pulse');

    setTimeout(() => {
      phoneModal.classList.remove('open');
      phoneConfirmationCard.style.display = 'none';
    }, 2000);
  }

  // ============================================================================
  // Audio Playback (ElevenLabs or Browser Fallback)
  // ============================================================================

  function playAudioBase64(base64Data) {
    if (!base64Data) return;
    window.hasReceivedElevenLabsAudio = true;
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    try {
      const audio = new Audio(`data:audio/mpeg;base64,${base64Data}`);
      audio.onplay = () => visualizer.setMode('speaking');
      audio.onended = () => {
        visualizer.setMode('listening');
        // Resume recognizer immediately after audio ends
        scheduleRecognizerRestart(100);
      };
      audio.play().catch(e => console.log('Audio autoplay blocked, click allowed:', e));
    } catch (e) {
      console.error('Audio playback error:', e);
    }
  }

  function speakBrowserFallback(text) {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.onstart = () => visualizer.setMode('speaking');
      utterance.onend = () => {
        visualizer.setMode('listening');
        // Resume recognizer immediately after speech synthesis finishes
        scheduleRecognizerRestart(100);
      };
      window.speechSynthesis.speak(utterance);
    }
  }

  // ============================================================================
  // Speech Recognition (Web Speech API Bridge to STT)
  // ============================================================================

  let restartTimeout = null;
  let recognitionActive = false;

  function scheduleRecognizerRestart(delay = 250) {
    if (!isCallActive || !isMicActive) return;
    clearTimeout(restartTimeout);
    restartTimeout = setTimeout(() => {
      if (isCallActive && isMicActive && !recognitionActive) {
        startSpeechRecognition();
      }
    }, delay);
  }

  function startSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('SpeechRecognition API not supported in this browser. Use text input.');
      return;
    }

    if (speechRecognizer) {
      try { speechRecognizer.abort(); } catch (e) {}
      speechRecognizer = null;
    }

    try {
      speechRecognizer = new SpeechRecognition();
      speechRecognizer.continuous = true;
      speechRecognizer.interimResults = false;
      speechRecognizer.lang = 'en-US';

      speechRecognizer.onstart = () => {
        recognitionActive = true;
        console.log('[SpeechRecognition] Active & listening...');
      };

      speechRecognizer.onresult = (event) => {
        if (!isMicActive) return;
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          const text = res[0].transcript.trim();
          if (text) {
            console.log('[Spoken Speech Detected]:', text);
            sendUserSpeech(text);
            hideQuickActions();
          }
        }
      };

      speechRecognizer.onerror = (e) => {
        console.log('[SpeechRecognition Error/Note]:', e.error);
        recognitionActive = false;
        if (e.error !== 'aborted') {
          scheduleRecognizerRestart(350);
        }
      };

      speechRecognizer.onend = () => {
        recognitionActive = false;
        scheduleRecognizerRestart(250);
      };

      speechRecognizer.start();
    } catch (e) {
      console.error('Error starting speech recognizer:', e);
      recognitionActive = false;
      scheduleRecognizerRestart(600);
    }
  }

  function stopSpeechRecognition() {
    clearTimeout(restartTimeout);
    recognitionActive = false;
    if (speechRecognizer) {
      try {
        speechRecognizer.abort();
      } catch (e) {}
      speechRecognizer = null;
    }
  }

  function sendUserSpeech(text) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(jsonStr({
      action: 'user_speech',
      text: text
    }));
  }

  // ============================================================================
  // Transcript UI Updates
  // ============================================================================

  function appendTranscript(speaker, text, timestamp) {
    const bubble = document.createElement('div');
    bubble.className = `transcript-bubble ${speaker}`;
    bubble.innerHTML = `
      ${escapeHtml(text)}
      <span class="transcript-time">${timestamp || 'Just now'}</span>
    `;
    phoneTranscriptBox.appendChild(bubble);
    phoneTranscriptBox.scrollTop = phoneTranscriptBox.scrollHeight;

    if (speaker === 'agent') {
      updateQuickActionsForAgentSpeech(text);
      if (!window.hasReceivedElevenLabsAudio) {
        speakBrowserFallback(text);
      }
    } else {
      hideQuickActions();
    }
  }

  function hideQuickActions() {
    if (phoneQuickActions) {
      phoneQuickActions.innerHTML = '';
      phoneQuickActions.style.display = 'none';
    }
  }

  function renderQuickChip(label, value, styleClass = 'primary') {
    const chip = document.createElement('button');
    chip.className = `quick-chip ${styleClass}`;
    chip.innerHTML = label;
    chip.onclick = () => {
      console.log('[Quick Action Clicked]:', value);
      sendUserSpeech(value);
      hideQuickActions();
    };
    return chip;
  }

  function updateQuickActionsForAgentSpeech(text) {
    if (!phoneQuickActions) return;
    phoneQuickActions.innerHTML = '';
    const lower = text.toLowerCase();

    // 1. Confirming Booking or Cancellation
    if (lower.includes('is that correct') || lower.includes('confirm before cancelling') || lower.includes('have it right')) {
      if (lower.includes('cancel')) {
        phoneQuickActions.appendChild(renderQuickChip('✓ Yes, Cancel Appointment', 'Yes, that is correct, please cancel it', 'danger'));
        phoneQuickActions.appendChild(renderQuickChip('✕ No, Keep It', 'No, keep it', 'secondary'));
      } else {
        phoneQuickActions.appendChild(renderQuickChip('✓ Yes, Confirm Booking', 'Yes, that is correct', 'primary'));
        phoneQuickActions.appendChild(renderQuickChip('✕ No, Change Slot', 'No, change it', 'secondary'));
      }
      phoneQuickActions.style.display = 'flex';
      return;
    }

    // 2. Offering available slots
    if (lower.includes('which time') || lower.includes('available for')) {
      const times = text.match(/\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)\b/g);
      if (times && times.length) {
        // Unique times
        const uniqueTimes = [...new Set(times)];
        uniqueTimes.forEach(t => {
          phoneQuickActions.appendChild(renderQuickChip(`📅 ${t}`, `Let's do ${t}`, 'primary'));
        });
        phoneQuickActions.style.display = 'flex';
        return;
      }
    }

    // 3. Opening greeting
    if (lower.includes('how can i help') || lower.includes('how else can i assist')) {
      phoneQuickActions.appendChild(renderQuickChip('🩺 Check Cardiology', "Hi, I'd like to check availability for cardiology", 'secondary'));
      phoneQuickActions.appendChild(renderQuickChip('✕ Cancel Appointment', "I would like to cancel my appointment", 'secondary'));
      phoneQuickActions.style.display = 'flex';
      return;
    }

    phoneQuickActions.style.display = 'none';
  }

  // ============================================================================
  // Booking & Cancellation Live Sync Handlers
  // ============================================================================

  function onAppointmentBooked(data) {
    window.telephonyAudio.playSuccessDing();
    showToast(`Appointment booked with ${data.doctor_name}!`, 'success');

    // Show inside phone confirmation card
    phoneConfirmationCard.style.display = 'block';
    phoneConfDetails.innerHTML = `
      <strong>Doctor:</strong> ${data.doctor_name}<br>
      <strong>Date & Time:</strong> ${data.date} at ${data.time_slot}<br>
      <strong>Patient Phone:</strong> ${data.patient_phone}
    `;

    // Refresh Doctors & Ledger with Highlight
    fetchDoctors();
    fetchAppointments(data.appointment_id, 'book');
  }

  function onAppointmentCancelled(data) {
    window.telephonyAudio.playHangupSound();
    showToast(`Appointment #${data.appointment_id} has been cancelled.`, 'danger');

    // Show inside phone card
    phoneConfirmationCard.style.display = 'block';
    phoneConfDetails.innerHTML = `
      <span style="color:#fb7185;">Cancelled booking for phone: ${data.patient_phone}</span>
    `;

    // Refresh Doctors & Ledger with Highlight
    fetchDoctors();
    fetchAppointments(data.appointment_id, 'cancel');
  }

  // ============================================================================
  // REST API Data Fetching & Rendering
  // ============================================================================

  async function fetchDoctors() {
    try {
      const res = await fetch('/api/doctors');
      const data = await res.json();
      allDoctors = data.doctors || [];
      renderDoctors(allDoctors);

      // Compute total available slots
      let totalSlots = 0;
      allDoctors.forEach(doc => {
        totalSlots += (doc.available_slots || []).length;
      });
      metricSlotsCount.textContent = totalSlots;
      slotsCountBadge.textContent = `${totalSlots} Available Slots`;
      metricDoctorsCount.textContent = allDoctors.length;
    } catch (e) {
      console.error('Error fetching doctors:', e);
    }
  }

  function renderDoctors(doctors) {
    doctorsListContainer.innerHTML = '';
    if (!doctors.length) {
      doctorsListContainer.innerHTML = `<div style="color:var(--text-dim); text-align:center; padding:30px;">No matching doctors found.</div>`;
      return;
    }

    doctors.forEach(doc => {
      const card = document.createElement('div');
      card.className = 'doctor-card';

      const slotsHtml = (doc.available_slots || []).map(s => `
        <span class="slot-chip ${s.status === 'booked' ? 'booked' : ''}">
          ${s.time}
        </span>
      `).join('');

      card.innerHTML = `
        <div class="doctor-info-row">
          <div class="doctor-profile">
            <div class="doctor-avatar">${doc.avatar_initials || 'MD'}</div>
            <div>
              <div class="doctor-name">${escapeHtml(doc.name)}</div>
              <div class="doctor-meta">${escapeHtml(doc.specialty)} • ${escapeHtml(doc.department)}</div>
            </div>
          </div>
          <div class="doctor-rating">★ ${doc.rating.toFixed(1)}</div>
        </div>
        <div class="slots-label">Available Slots (${(doc.available_slots || []).length}):</div>
        <div class="slots-grid">
          ${slotsHtml || '<span style="font-size:0.75rem; color:var(--text-dim);">No open slots today</span>'}
        </div>
      `;

      doctorsListContainer.appendChild(card);
    });
  }

  async function fetchAppointments(highlightId = null, highlightType = null) {
    try {
      const res = await fetch('/api/appointments');
      const data = await res.json();
      const appointments = data.appointments || [];
      renderAppointments(appointments, highlightId, highlightType);
      metricBookingsCount.textContent = appointments.length;
      appCountBadge.textContent = `${appointments.length} Bookings`;
    } catch (e) {
      console.error('Error fetching appointments:', e);
    }
  }

  function renderAppointments(appointments, highlightId, highlightType) {
    appointmentsTableBody.innerHTML = '';
    if (!appointments.length) {
      appointmentsTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align:center; color:var(--text-dim); padding: 35px;">
            No appointments booked yet. Click "Try Call" to speak with the agent.
          </td>
        </tr>
      `;
      return;
    }

    appointments.forEach(app => {
      const tr = document.createElement('tr');
      if (highlightId && app.id === highlightId) {
        tr.className = highlightType === 'book' ? 'highlight-booking' : 'highlight-cancel';
      }

      tr.innerHTML = `
        <td><span class="phone-badge">${escapeHtml(app.patient_phone)}</span></td>
        <td><strong>${escapeHtml(app.doctor_name)}</strong></td>
        <td><span style="color:var(--text-muted);">${escapeHtml(app.specialty)}</span></td>
        <td>${escapeHtml(app.date)} • <strong>${escapeHtml(app.time_slot)}</strong></td>
        <td>
          <span class="status-badge ${app.status}">
            ● ${escapeHtml(app.status)}
          </span>
        </td>
        <td>
          ${app.status === 'confirmed' ? `
            <button class="btn-cancel-sm" data-id="${app.id}" data-phone="${app.patient_phone}">
              Cancel
            </button>
          ` : '<span style="font-size:0.75rem; color:var(--text-dim);">--</span>'}
        </td>
      `;

      appointmentsTableBody.appendChild(tr);
    });

    // Attach listeners to cancel buttons
    document.querySelectorAll('.btn-cancel-sm').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = parseInt(e.target.dataset.id);
        const phone = e.target.dataset.phone;
        await cancelAppointmentDirect(id, phone);
      });
    });
  }

  async function cancelAppointmentDirect(id, phone) {
    if (!confirm(`Cancel appointment #${id} for phone ${phone}?`)) return;
    try {
      const res = await fetch('/api/appointments/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ appointment_id: id, patient_phone: phone })
      });
      const data = await res.json();
      if (data.success) {
        showToast('Appointment cancelled successfully', 'danger');
        fetchDoctors();
        fetchAppointments(id, 'cancel');
      }
    } catch (e) {
      showToast('Error cancelling appointment', 'danger');
    }
  }

  // ============================================================================
  // Event Listeners & UI Triggers
  // ============================================================================

  // Open Call Modal & Start Session
  btnOpenCallModal.addEventListener('click', () => {
    isCallActive = true;
    phoneTranscriptBox.innerHTML = '';
    phoneConfirmationCard.style.display = 'none';
    phoneModal.classList.add('open');
    onStateChange('connecting');
    connectCallSession();
  });

  // End Call
  btnEndCall.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(jsonStr({ action: 'end_call' }));
    }
    handleCallEnded();
  });

  // Toggle Mic
  btnToggleMic.addEventListener('click', () => {
    isMicActive = !isMicActive;
    if (isMicActive) {
      btnToggleMic.classList.add('active');
      btnToggleMic.textContent = '🎙️';
      showToast('Microphone unmuted', 'success');
      startSpeechRecognition();
    } else {
      btnToggleMic.classList.remove('active');
      btnToggleMic.textContent = '🔇';
      showToast('Microphone muted', 'danger');
      stopSpeechRecognition();
    }
  });

  // Send Text via Input Bar
  function handleSendTextInput() {
    const text = phoneTextInput.value.trim();
    if (!text) return;
    phoneTextInput.value = '';
    sendUserSpeech(text);
  }

  btnSendText.addEventListener('click', handleSendTextInput);
  phoneTextInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleSendTextInput();
  });

  // Filter Doctors by Search Input
  doctorSearchInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase().trim();
    if (!query) {
      renderDoctors(allDoctors);
      return;
    }
    const filtered = allDoctors.filter(d => 
      d.name.toLowerCase().includes(query) ||
      d.specialty.toLowerCase().includes(query) ||
      d.department.toLowerCase().includes(query)
    );
    renderDoctors(filtered);
  });

  // Reset Demo State
  btnResetDb.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/reset', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast('Demo database reset to clean state', 'success');
        fetchDoctors();
        fetchAppointments();
      }
    } catch (e) {
      console.error(e);
    }
  });

  // ============================================================================
  // Helpers
  // ============================================================================

  function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function jsonStr(obj) {
    return JSON.stringify(obj);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
});
