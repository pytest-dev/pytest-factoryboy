try:
    from factory.declarations import PostGenerationContext
except ImportError:
    from factory.builder import PostGenerationContext
