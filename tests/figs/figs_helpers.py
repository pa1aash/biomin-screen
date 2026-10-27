"""Helpers shared by the tests of the figure system."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def plt():
    from biomin_screen.figures import style
    return style.use(REPO)


def clean_figure(kind="single", height_cm=6.0):
    """A figure that passes the checker: one axes, data line, axis titles."""
    from biomin_screen.figures import style
    p = plt()
    fig, ax = p.subplots(figsize=style.figsize(kind, height_cm, REPO))
    ax.plot([0, 1, 2], [0, 1, 4])
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    return fig, ax


def check(fig):
    from biomin_screen.figures import checker
    return checker.check_rsc(fig, REPO)
