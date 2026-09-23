# Android Studio

O APK empacota a interface Capacitor em `www`. O backend Python continua sendo executado separadamente.

## Emulador Android

1. No projeto raiz, inicie o backend usando o ambiente pedido:

   ```bash
   source venv/bin/activate
   PYTHONPATH=py python py/app.py
   ```

2. Sincronize os arquivos web:

   ```bash
   cd passos_contados_interface
   npx cap copy android
   ```

3. Abra `passos_contados_interface/android` no Android Studio e execute o app.

O APK usa automaticamente `http://10.0.2.2:5000/api` no emulador. O `10.0.2.2` aponta para o computador host.

## Aparelho físico

### USB sem internet

Ative as Opções do desenvolvedor e a Depuração USB no celular. Com o aparelho conectado e autorizado:

```bash
adb devices
adb reverse tcp:5000 tcp:5000
```

O APK está configurado para usar `http://127.0.0.1:5000/api` nesse modo. O endereço local é encaminhado pelo ADB para o Flask no computador.

Coloque o celular e o computador na mesma rede, inicie o Flask escutando em `0.0.0.0:5000` e altere `window.PASSOS_CONTADOS_API_URL` em `www/index.html` para:

```js
window.PASSOS_CONTADOS_API_URL = "http://IP_DO_COMPUTADOR:5000/api";
```

Depois execute novamente `npx cap copy android` e faça o build no Android Studio. O Manifest já permite Internet e HTTP local para o backend de testes.

O SQLite, o ArUco, o YOLO e o Whisper pertencem ao backend Python. A câmera e o microfone são capturados pelo celular e enviados ao backend. A fala de resposta usa o áudio do próprio celular. Sem o backend acessível, o APK abre a interface, mas não consegue executar o processamento inteligente.

## Descoberta do carrinho ESP32

Com o backend e o carrinho na mesma rede Wi-Fi, o backend envia a cada 10 segundos a mensagem UDP `PASSOS_CONTADOS_DISCOVER` para o broadcast na porta `4210`. O ESP32 deve responder para o endereço e porta de origem com um JSON como:

```json
{"tipo":"esp32-carrinho","id":"carrinho-01","nome":"Carrinho Passos Contados","porta":80}
```

O endpoint `GET /api/carrinho?atualizar=1` informa os carrinhos encontrados. A interface exibe o primeiro carrinho encontrado na tela Mapa. O roteador deve permitir comunicação entre os dispositivos (desative isolamento de clientes/AP isolation). O firmware do ESP32 ainda precisa implementar esse listener UDP; ele não está neste repositório.
