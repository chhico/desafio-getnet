class DomainException(Exception):
    """
    Exceção base para o domínio da aplicação.
    Capturada globalmente para evitar vazar stack traces em produção.
    """
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundException(DomainException):
    def __init__(self, message: str = "Recurso não encontrado"):
        super().__init__(message, status_code=404)


class BusinessRuleException(DomainException):
    def __init__(self, message: str = "Regra de negócio violada"):
        super().__init__(message, status_code=422)
