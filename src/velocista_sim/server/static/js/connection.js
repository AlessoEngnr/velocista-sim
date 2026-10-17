// Conexión WebSocket con el servidor (research R4, R15).
// La URL es siempre `/ws` del mismo origen que la página, con esquema seguro si la página llegó
// por https. Solo se agregan los parámetros de conexión del contrato `track` y `robot`, y solo al
// cambiar de pista. Un frame de texto = un mensaje JSON. Sin reconexión automática: quien llama
// decide cuándo reconectar.

let socket = null;

/** URL del WebSocket del mismo origen; `track` y `robot` solo si se pasan. */
export function buildUrl({ track, robot } = {}) {
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  const url = new URL("/ws", `${scheme}//${location.host}`);
  if (track) url.searchParams.set("track", track);
  if (robot) url.searchParams.set("robot", robot);
  return url.toString();
}

/**
 * Abre la conexión (cerrando la anterior, si había) y llama a los `handlers`:
 * `onOpen()`, `onMessage(message)` con el JSON ya parseado, `onInvalid(frame)` si el frame no es
 * JSON de texto y `onClose(code)`. Los eventos de una conexión anterior se ignoran.
 */
export function connect(url, handlers) {
  close();
  const current = new WebSocket(url);
  socket = current;
  current.onopen = () => {
    if (socket === current) handlers.onOpen?.();
  };
  current.onmessage = (event) => {
    if (socket !== current) return;
    if (typeof event.data !== "string") {
      handlers.onInvalid?.(event.data);
      return;
    }
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      handlers.onInvalid?.(event.data);
      return;
    }
    handlers.onMessage?.(message);
  };
  current.onclose = (event) => {
    if (socket !== current) return;
    socket = null;
    handlers.onClose?.(event.code);
  };
}

/** Envía un comando si la conexión está abierta; devuelve si se envió. */
export function send(command) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(command));
  return true;
}

/** Cierra la conexión actual sin avisar a sus handlers. */
export function close() {
  if (!socket) return;
  const previous = socket;
  socket = null;
  previous.close();
}
