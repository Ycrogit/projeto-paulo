const screens = document.querySelectorAll(".screen");
const navItems = document.querySelectorAll(".nav-item");
const main = document.querySelector("#main-content");
const toast = document.querySelector("#toast");
const API_BASE = window.PASSOS_CONTADOS_API_URL
  || localStorage.getItem("passos_contados_api_url")
  || (window.Capacitor ? "http://10.0.2.2:5000/api" : "/api");
const cameraFeed = document.querySelector("#cameraFeed");
const processedCameraFeed = document.querySelector("#processedCameraFeed");
const cameraCanvas = document.createElement("canvas");
let cameraStream;
let frameTimer;
let frameRequestAtivo = false;
let ultimoLocalFalado = "";
let modoProcessamento = "aruco";
let carrinhoConectado = false;

let currentScreen = "navegar";
let toastTimer;

async function verificarCarrinho() {
  try {
    const response = await fetch(`${API_BASE}/carrinho?atualizar=1`);
    const status = await response.json();
    carrinhoConectado = Boolean(status.conectado);
    const aviso = document.querySelector("#cartStatus");
    if (aviso) {
      aviso.textContent = carrinhoConectado
        ? `Carrinho conectado: ${status.carrinhos[0].nome}`
        : "Carrinho não encontrado nesta rede";
      aviso.classList.toggle("is-connected", carrinhoConectado);
    }
  } catch (error) {
    console.warn("Descoberta do carrinho:", error.message);
  }
}

verificarCarrinho();
setInterval(verificarCarrinho, 15000);

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
let vozesProntas;

function normalizeCommand(command) {
  return command.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
}

function setModuleState(moduleName, status) {
  const module = document.querySelector(`[data-module="${moduleName}"]`);
  const statusText = document.querySelector(`#${moduleName}Status`);
  module.classList.add("is-active");
  statusText.textContent = status;
}

async function prepararVozesWeb() {
  if (vozesProntas) return vozesProntas;
  vozesProntas = new Promise(resolve => {
    const obterVozes = () => {
      const vozes = window.speechSynthesis?.getVoices?.() || [];
      if (vozes.length) resolve(vozes);
    };
    window.speechSynthesis?.addEventListener("voiceschanged", obterVozes, { once: true });
    obterVozes();
    setTimeout(() => resolve(window.speechSynthesis?.getVoices?.() || []), 800);
  });
  return vozesProntas;
}

async function speakResponse(message) {
  if (!message) return Promise.resolve();

  const nativeTextToSpeech = window.Capacitor?.Plugins?.TextToSpeech;
  if (nativeTextToSpeech) {
    try {
      await nativeTextToSpeech.stop();
      await nativeTextToSpeech.speak({
        text: message,
        lang: "pt-BR",
        rate: 0.85,
        pitch: 1.0,
        volume: 1.0,
      });
      return;
    } catch (error) {
      console.warn("TTS nativo indisponível; usando voz web:", error);
    }
  }

  if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
    announce(`Jarvis: ${message}`);
    return Promise.resolve();
  }

  const vozes = await prepararVozesWeb();
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(message);
  utterance.lang = "pt-BR";
  utterance.voice = vozes.find(voz => voz.lang?.toLowerCase().startsWith("pt-br"))
    || vozes.find(voz => voz.lang?.toLowerCase().startsWith("pt"))
    || null;
  utterance.rate = 0.72;
  return new Promise(resolve => {
    utterance.onend = resolve;
    utterance.onerror = resolve;
    window.speechSynthesis.speak(utterance);
  });
}

function refreshCameraFeed() {
  iniciarCameraCelular().catch(error => announce(`Câmera indisponível: ${error.message}`));
}

async function iniciarCameraCelular() {
  if (!cameraFeed || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("Este aparelho não oferece câmera ao aplicativo.");
  }
  if (!cameraStream) {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    });
    cameraFeed.srcObject = cameraStream;
    await cameraFeed.play();
  }
  clearInterval(frameTimer);
  frameTimer = setInterval(enviarFrameCelular, 650);
}

async function enviarFrameCelular() {
  if (frameRequestAtivo || !cameraFeed?.videoWidth || !cameraFeed.videoHeight) return;
  frameRequestAtivo = true;
  cameraCanvas.width = cameraFeed.videoWidth;
  cameraCanvas.height = cameraFeed.videoHeight;
  cameraCanvas.getContext("2d").drawImage(cameraFeed, 0, 0);
  const blob = await new Promise(resolve => cameraCanvas.toBlob(resolve, "image/jpeg", 0.72));
  if (!blob) return;
  const dados = new FormData();
  dados.append("frame", blob, "camera.jpg");
  dados.append("modo", modoProcessamento);
  try {
    const response = await fetch(`${API_BASE}/processar-frame`, { method: "POST", body: dados });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || "Falha ao processar câmera.");
    const local = result.locais?.[0];
    if (local && local.fala !== ultimoLocalFalado) {
      ultimoLocalFalado = local.fala;
      speakResponse(local.fala);
    }
    if (result.imagem && processedCameraFeed) processedCameraFeed.src = result.imagem;
  } catch (error) {
    console.warn("Processamento da câmera:", error.message);
  } finally {
    frameRequestAtivo = false;
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

  if (result.acao === "PARAR_FALA") {
    stopSpeaking();
    aguardandoComando = false;
    announce(responseMessage || "Fala interrompida.");
    return;
  }

  if (result.acao === "ATIVAR_JARVIS" || normalized === "jarvis") {
    aguardandoComando = true;
    announce(responseMessage);
    speakResponse(responseMessage);
    return;
  }

  if (result.acao === "ABRIR_LEITOR_ARUCO" || result.acao === "ATIVAR_LEITOR_COMPLETO" || normalized === "abrir leitor aruco") {
    modoProcessamento = result.acao === "ATIVAR_LEITOR_COMPLETO" ? "completo" : "aruco";
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
    modoProcessamento = "objetos";
    setModuleState("local", "Ativo no backend");
    document.querySelector("#theoryMode").textContent = "Processamento de local selecionado";
    refreshCameraFeed();
    showScreen("mapa");
    announce(responseMessage);
    speakResponse(responseMessage);
    aguardandoComando = false;
    return;
  }

  if (result.acao === "ATIVAR_DISTANCIA_OBJETOS" || normalized === "ativar distancia de objetos") {
    modoProcessamento = "objetos";
    setModuleState("local", "Distância de objetos ativa");
    document.querySelector("#theoryMode").textContent = "Distância de objetos selecionada";
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

function stopSpeaking() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  fetch(`${API_BASE}/parar-fala`, { method: "POST" }).catch(() => {});
}

async function captureVoiceCommand() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    throw new Error("Este aparelho não oferece microfone ao aplicativo.");
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  const gravador = new MediaRecorder(stream, { mimeType: "audio/webm" });
  const partes = [];
  gravador.ondataavailable = evento => { if (evento.data.size) partes.push(evento.data); };
  const terminou = new Promise(resolve => { gravador.onstop = resolve; });
  gravador.start();
  await new Promise(resolve => setTimeout(resolve, 5000));
  if (gravador.state !== "inactive") gravador.stop();
  await terminou;
  stream.getTracks().forEach(track => track.stop());
  const dadosAudio = new FormData();
  dadosAudio.append("audio", new Blob(partes, { type: "audio/webm" }), "comando.webm");
  const response = await fetch(`${API_BASE}/comando-voz`, { method: "POST", body: dadosAudio });
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
  stopSpeaking();

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
