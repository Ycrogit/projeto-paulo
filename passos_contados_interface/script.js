const API_URL = "/api";
const screens = document.querySelectorAll(".screen");
const navItems = document.querySelectorAll(".nav-item");
const toast = document.querySelector("#toast");
const cameraFeed = document.querySelector("#cameraFeed");
let toastTimer;

async function verificarCarrinho() {
    try {
        const resposta = await fetch(`${API_URL}/carrinho?atualizar=1`);
        const dados = await resposta.json();
        const indicador = document.querySelector("#cartStatus");
        if (indicador) indicador.textContent = dados.conectado
            ? `Carrinho conectado: ${dados.carrinhos[0].nome}`
            : "Carrinho não encontrado nesta rede";
    } catch (erro) {
        console.warn("Descoberta do carrinho:", erro.message);
    }
}

verificarCarrinho();
setInterval(verificarCarrinho, 15000);

function announce(message) {
    if (!toast) return;
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.add("show");
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function showScreen(name) {
    screens.forEach(screen => {
        const active = screen.dataset.screen === name;
        screen.hidden = !active;
        screen.classList.toggle("active", active);
    });
    navItems.forEach(item => item.classList.toggle("active", item.dataset.target === name));
}

async function enviarComando(texto) {
    try {
        const resposta = await fetch(`${API_URL}/comando`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ comando: texto })
        });
        const dados = await resposta.json();
        if (!resposta.ok) throw new Error(dados.erro || "Backend indisponivel");
        document.querySelector("#recognizedText").textContent = texto;
        document.querySelector("#voiceCaption").hidden = false;
        announce(dados.resposta || dados.acao || "Comando processado");
        if (["ABRIR_LEITOR_ARUCO", "ABRIR_PROCESSAMENTO_LOCAL", "OBTER_LOCALIZACAO"].includes(dados.acao)) {
            showScreen("mapa");
            if (cameraFeed) cameraFeed.src = `${API_URL}/camera.mjpg`;
        }
    } catch (erro) {
        announce(`Erro: ${erro.message}`);
    }
}

navItems.forEach(item => item.addEventListener("click", () => showScreen(item.dataset.target)));

document.querySelector("#runCommand")?.addEventListener("click", () => {
    const input = document.querySelector("#commandInput");
    if (input.value.trim()) enviarComando(input.value.trim());
});

document.querySelector("#commandInput")?.addEventListener("keydown", event => {
    if (event.key === "Enter") document.querySelector("#runCommand")?.click();
});

document.querySelectorAll(".place-card").forEach(card => card.addEventListener("click", () => {
    const destino = card.dataset.place;
    document.querySelector("#destinationInput").value = destino;
    document.querySelector("#routeTitle").textContent = `Destino: ${destino}`;
    document.querySelector("#routeDescription").textContent = "Destino selecionado para teste da interface.";
    showScreen("mapa");
}));

document.querySelector("#searchDestination")?.addEventListener("click", () => {
    const input = document.querySelector("#destinationInput");
    if (input.value.trim()) {
        document.querySelector("#routeTitle").textContent = `Destino: ${input.value.trim()}`;
        showScreen("mapa");
    }
});

document.querySelectorAll(".toggle").forEach(toggle => toggle.addEventListener("click", () => {
    const ativo = toggle.getAttribute("aria-pressed") !== "true";
    toggle.setAttribute("aria-pressed", String(ativo));
    toggle.classList.toggle("is-on", ativo);
    document.body.classList.toggle(toggle.dataset.setting, ativo);
}));