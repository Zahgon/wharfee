# -*- coding: utf-8
"""
Key bindings for the CLI.
"""
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


def get_key_bindings(set_long_options, get_long_options, set_fuzzy_match, get_fuzzy_match):
    """
    Create and initialize key bindings.
    :return: KeyBindings
    """

    assert callable(set_long_options)
    assert callable(get_long_options)
    assert callable(set_fuzzy_match)
    assert callable(get_fuzzy_match)

    kb = KeyBindings()

    @kb.add(Keys.F2)
    def _(event):
        """
        When F2 has been pressed, fill in the "help" command.
        """
        pass

    @kb.add(Keys.F3)
    def _(event):
        """
        Enable/Disable long option name suggestion.
        """
        pass

    @kb.add(Keys.F4)
    def _(event):
        """
        Enable/Disable fuzzy matching.
        """
        pass

    @kb.add(Keys.F10)
    def _(event):
        """
        When F10 has been pressed, quit.
        """
        raise EOFError

    @kb.add(Keys.ControlSpace)
    def _(event):
        """
        Initialize autocompletion at cursor.

        If the autocompletion menu is not showing, display it with the
        appropriate completions for the context.

        If the menu is showing, select the next completion.
        """
        pass

    return kb
