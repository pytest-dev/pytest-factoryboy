try:
    from factory.declarations import PostGenerationContext
except ImportError:  # factory_boy < 3.2.0
    from factory.builder import PostGenerationContext
