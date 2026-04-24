# -*- coding: utf-8
"""
Bottom toolbar for the CLI.
"""
from prompt_toolkit.formatted_text import FormattedText


def create_toolbar_handler(is_long_option, is_fuzzy):
    """
    Create a toolbar handler function.
    :param is_long_option: callable
    :param is_fuzzy: callable
    :return: callable
    """

    assert callable(is_long_option)
    assert callable(is_fuzzy)

    def get_toolbar_items():
        """
        Return bottom menu items.
        :return: FormattedText
        """
        pass

    return get_toolbar_items
