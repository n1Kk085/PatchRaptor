class ServiceLocator:
    """
    A centralized registry for accessing core PatchRaptor Managers.
    Prevents the 'God Object' anti-pattern by allowing handlers to request
    specific managers on-demand rather than relying on massive constructors.
    """
    _registry = {}

    @classmethod
    def register(cls, name: str, service):
        cls._registry[name] = service

    @classmethod
    def get(cls, name: str):
        if name not in cls._registry:
            raise KeyError(f"Service '{name}' has not been registered in the ServiceLocator.")
        return cls._registry[name]

    @classmethod
    def clear(cls):
        cls._registry.clear()
