class RespuestasPrivadasMiddleware:
    """Evita almacenar respuestas de cuentas y paneles en cachés compartidas."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        if request.path.startswith("/api/"):
            respuesta["Cache-Control"] = "no-store, private"
        return respuesta
