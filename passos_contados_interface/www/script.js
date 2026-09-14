const screens = document.querySelectorAll(".screen");
const navItems = document.querySelectorAll(".nav-item");
const main = document.querySelector("#main-content");
const toast = document.querySelector("#toast");
const API_BASE = window.PASSOS_CONTADOS_API_URL || "http://192.168.93.171:8000/api";
const cameraFeed = document.querySelector("#cameraFeed");

let currentScreen = "navegar";
let toastTimer;

function announce(message) {
  const status = document.querySelector("#voiceStatusText");
  if (status) status.textContent = message;

  if (document.body.classList.contains("visual-feedback-off")) return;

  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("show");
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function showScreen(name) {
  currentScreen = name;

  screens.forEach(screen => {
    const active = screen.dataset.screen === name;
    screen.hidden = !active;
    screen.classList.toggle("active", active);
  });

  navItems.forEach(item => {
    const active = item.dataset.target === name;
    item.classList.toggle("active", active);

    if (active) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  });

  main.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });

  const labels = {
    navegar: "Tela Navegar aberta.",
    mapa: "Tela Mapa aberta.",
    ajuda: "Tela Ajuda aberta."
  };

  announce(labels[name]);
}

navItems.forEach(item => {
  item.addEventListener("click", () => showScreen(item.dataset.target));
});

// Locais
const placeCards = document.querySelectorAll(".place-card");
const destinationInput = document.querySelector("#destinationInput");
const searchDestination = document.querySelector("#searchDestination");

function chooseDestination(place) {
  destinationInput.value = place;
  document.querySelector("#recognizedText").textContent = place;
  document.querySelector("#voiceCaption").hidden = false;

  const routeTitle = document.querySelector("#routeTitle");
  const routeDescription = document.querySelector("#routeDescription");

  routeTitle.textContent = `Destino: ${place}`;
  routeDescription.textContent = "Rota ilustrativa selecionada. O GPS real não está conectado.";

  announce(`Destino selecionado: ${place}.`);
}

placeCards.forEach(card => {
  card.addEventListener("click", () => chooseDestination(card.dataset.place));
});

searchDestination.addEventListener("click", () => {
  const value = destinationInput.value.trim();

  if (!value) {
    announce("Digite um local para escolher um destino.");
    destinationInput.focus();
    return;
  }

  chooseDestination(value);
});

destinationInput.addEventListener("keydown", event => {
  if (event.key === "Enter") searchDestination.click();
});

// Voz — demonstração visual
const micButton = document.querySelector("#micButton");
const speakButton = document.querySelector("#speakButton");
const voiceStatus = document.querySelector("#voiceStatus");
const voiceStatusText = document.querySelector("#voiceStatusText");
const voiceCaption = document.querySelector("#voiceCaption");
const recognizedText = document.querySelector("#recognizedText");
const commandInput = document.querySelector("#commandInput");
const runCommand = document.querySelector("#runCommand");

let listening = false;
let aguardandoComando = false;
let recognition;

function normalizeCommand(command) {
  return command.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
}

function setModuleState(moduleName, status) {
  const module = document.querySelector(`[data-module="${moduleName}"]`);
  const statusText = document.querySelector(`#${moduleName}Status`);
  module.classList.add("is-active");
  statusText.textContent = status;
}

function speakResponse(message) {
  if (!message || !window.speechSynthesis) return Promise.resolve();

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(message);
  utterance.lang = "pt-BR";
  utterance.rate = 0.95;
  return new Promise(resolve => {
    utterance.onend = resolve;
    utterance.onerror = resolve;
    window.speechSynthesis.speak(utterance);
  });
}

function refreshCameraFeed() {
  if (cameraFeed && !cameraFeed.src.startsWith(`${API_BASE}/camera.mjpg`)) {
    cameraFeed.src = `${API_BASE}/camera.mjpg`;
  }
}

function processCommandResult(result, veioDaVoz = false) {
  if (result.acao === "SEM_COMANDO") return;

  if (veioDaVoz && !aguardandoComando && result.acao !== "ATIVAR_JARVIS") return;

  const command = result.texto || result.texto_original || "";
  const normalized = normalizeCommand(command);
  const responseMessage = result.resposta || result.status || "";
  recognizedText.textContent = command;
  voiceCaption.hidden = false;

  if (result.acao === "ATIVAR_JARVIS" || normalized === "jarvis") {
    aguardandoComando = true;
    announce(responseMessage);
    speakResponse(responseMessage);
    return;
  }

  if (result.acao === "ABRIR_LEITOR_ARUCO" || normalized === "abrir leitor aruco") {
    setModuleState("aruco", "Ativo no backend");
    document.querySelector("#theoryMode").textContent = "Leitor ArUco selecionado";
    refreshCameraFeed();
    showScreen("mapa");
    announce(responseMessage);
    speakResponse(responseMessage);
    aguardandoComando = false;
    return;
  }

  if (result.acao === "ABRIR_PROCESSAMENTO_LOCAL" || normalized === "averiguar local") {
    setModuleState("local", "Ativo no backend");
    document.querySelector("#theoryMode").textContent = "Processamento de local selecionado";
    refreshCameraFeed();
    showScreen("mapa");
    announce(responseMessage);
    speakResponse(responseMessage);
    aguardandoComando = false;
    return;
  }

  announce(responseMessage || "Comando não reconhecido.");
  if (!veioDaVoz) speakResponse(responseMessage);
}

async function enviarComando(command) {
  try {
    const response = await fetch(`${API_BASE}/comando`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comando: command })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || "Backend indisponível.");
    processCommandResult(result);
  } catch (error) {
    announce(`Não foi possível comunicar com o backend: ${error.message}`);
  }
}

async function captureVoiceCommand() {
  const response = await fetch(`${API_BASE}/comando-voz`, { method: "POST" });
  const result = await response.json();
  if (!response.ok) throw new Error(result.erro || "Falha no reconhecimento.");
  processCommandResult(result, true);
  if (result.acao === "ATIVAR_JARVIS") {
    await new Promise(resolve => setTimeout(resolve, 1400));
  }
}

async function startListening() {
  if (listening) return;

  listening = true;
  micButton.classList.add("is-listening");
  micButton.setAttribute("aria-pressed", "true");
  micButton.setAttribute("aria-label", "Desativar comando de voz");
  voiceStatus.classList.add("listening");
  voiceStatusText.textContent = "Escutando… fale um comando para o Whisper";
  speakButton.textContent = "Escutando…";

  announce("Jarvis em prontidão. Fale um comando.");

  while (listening) {
    try {
      await captureVoiceCommand();
      if (listening) voiceStatusText.textContent = "Pronto para o próximo comando";
    } catch (error) {
      stopListening(false);
      announce(`Whisper indisponível: ${error.message}`);
    }
  }
}

function stopListening(showMessage = true) {
  listening = false;
  micButton.classList.remove("is-listening");
  micButton.setAttribute("aria-pressed", "false");
  micButton.setAttribute("aria-label", "Ativar comando de voz");
  voiceStatus.classList.remove("listening");
  speakButton.textContent = "Toque para falar";
  voiceStatusText.textContent = "Sistema pronto e aguardando comando";
  if (window.speechSynthesis) window.speechSynthesis.cancel();

  if (showMessage) announce("Comando de voz desativado.");
}

micButton.addEventListener("click", () => {
  if (listening) {
    stopListening();
  } else {
    startListening();
  }
});

speakButton.addEventListener("click", () => {
  if (listening) {
    stopListening();
  } else {
    startListening();
  }
});

runCommand.addEventListener("click", () => {
  const command = commandInput.value.trim();
  if (!command) {
    announce("Digite um comando para o teste teórico.");
    commandInput.focus();
    return;
  }
  enviarComando(command);
});

commandInput.addEventListener("keydown", event => {
  if (event.key === "Enter") runCommand.click();
});

// Mapa
const locationChoices = document.querySelectorAll(".location-choice");

locationChoices.forEach(choice => {
  choice.addEventListener("click", () => {
    locationChoices.forEach(button => {
      button.classList.remove("active");
      button.setAttribute("aria-pressed", "false");
    });

    choice.classList.add("active");
    choice.setAttribute("aria-pressed", "true");

    const type = choice.dataset.mapChoice;

    if (type === "onde-estou") {
      document.querySelector("#routeTitle").textContent = "Você está na entrada";
      document.querySelector("#routeDescription").textContent =
        "Marcador azul representa sua posição atual no mapa de demonstração.";
      announce("Modo Onde estou selecionado.");
    } else {
      const destination = destinationInput.value.trim() || "Biblioteca";
      document.querySelector("#routeTitle").textContent = `Destino: ${destination}`;
      document.querySelector("#routeDescription").textContent =
        "O visor representa visualmente o local desejado.";
      announce("Modo Onde quero ir selecionado.");
    }
  });
});

// Acessibilidade
const toggles = document.querySelectorAll(".toggle");

toggles.forEach(toggle => {
  toggle.addEventListener("click", () => {
    const setting = toggle.dataset.setting;
    const isOn = toggle.classList.toggle("is-on");
    toggle.setAttribute("aria-pressed", String(isOn));

    if (setting === "large-text") {
      document.body.classList.toggle("large-text", isOn);
      announce(isOn ? "Texto aumentado." : "Tamanho do texto restaurado.");
    }

    if (setting === "high-contrast") {
      document.body.classList.toggle("high-contrast", isOn);
      announce(isOn ? "Alto contraste ativado." : "Alto contraste desativado.");
    }

    if (setting === "visual-feedback") {
      document.body.classList.toggle("visual-feedback-off", !isOn);
      if (isOn) announce("Feedback visual ativado.");
    }

    if (setting === "keyboard") {
      announce(
        isOn
          ? "Navegação por teclado ativada. Use Tab para avançar e Enter para selecionar."
          : "A interface continua utilizável pelo teclado, conforme os recursos do navegador."
      );
    }
  });
});

// Perfil — apenas demonstração
document.querySelector("#profileButton").addEventListener("click", () => {
  announce("Perfil de demonstração: Maria da Silva.");
});

// Teclas de atalho úteis para demonstração
document.addEventListener("keydown", event => {
  if (event.altKey && event.key === "1") {
    event.preventDefault();
    showScreen("navegar");
  }

  if (event.altKey && event.key === "2") {
    event.preventDefault();
    showScreen("mapa");
  }

  if (event.altKey && event.key === "3") {
    event.preventDefault();
    showScreen("ajuda");
  }

  if (event.key === "Escape" && listening) {
    stopListening();
  }
});

window.setTimeout(() => startListening(), 800);

// Estado inicial
document.querySelector('[data-map-choice="onde-estou"]').setAttribute("aria-pressed", "true");
