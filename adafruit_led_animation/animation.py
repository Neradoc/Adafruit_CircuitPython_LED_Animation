# The MIT License (MIT)
#
# Copyright (c) 2019-2020 Roy Hooper
# Copyright (c) 2020 Kattni Rembor for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_led_animation.animation`
================================================================================

Animation base class, and basic animations for CircuitPython helper library for LED animations.

* Author(s): Roy Hooper, Kattni Rembor

Implementation Notes
--------------------

**Hardware:**

* `Adafruit NeoPixels <https://www.adafruit.com/category/168>`_
* `Adafruit DotStars <https://www.adafruit.com/category/885>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

"""

from math import ceil
from . import NANOS_PER_SECOND, monotonic_ns
from .color import BLACK, RAINBOW

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_LED_Animation.git"


class Animation:
    # pylint: disable=too-many-instance-attributes
    """
    Base class for animations.
    """
    cycle_complete_supported = False

    # pylint: disable=too-many-arguments
    def __init__(self, pixel_object, speed, color, peers=None, paused=False, name=None):
        self.pixel_object = pixel_object
        self.pixel_object.auto_write = False
        self.peers = peers if peers else []
        """A sequence of animations to trigger .draw() on when this animation draws."""
        self._speed_ns = 0
        self._color = None
        self._paused = paused
        self._next_update = monotonic_ns()
        self._time_left_at_pause = 0
        self._also_notify = []
        self.speed = speed  # sets _speed_ns
        self.color = color  # Triggers _recompute_color
        self.name = name
        self.notify_cycles = 1
        """Number of cycles to trigger additional cycle_done notifications after"""
        self.draw_count = 0
        """Number of animation frames drawn."""
        self.cycle_count = 0
        """Number of animation cycles completed."""

    def __str__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.name)

    def animate(self):
        """
        Call animate() from your code's main loop.  It will draw the animation draw() at intervals
        configured by the speed property (set from init).

        :return: True if the animation draw cycle was triggered, otherwise False.
        """
        if self._paused:
            return False

        now = monotonic_ns()
        if now < self._next_update:
            return False

        self.draw()
        self.draw_count += 1

        # Draw related animations together
        if self.peers:
            for peer in self.peers:
                peer.draw()

        self._next_update = now + self._speed_ns
        return True

    def draw(self):
        """
        Animation subclasses must implement draw() to render the animation sequence.
        Draw must call show().
        """
        raise NotImplementedError()

    def show(self):
        """
        Displays the updated pixels.  Called during animates with changes.
        """
        self.pixel_object.show()

    def freeze(self):
        """
        Stops the animation until resumed.
        """
        self._paused = True
        self._time_left_at_pause = max(0, monotonic_ns() - self._next_update)

    def resume(self):
        """
        Resumes the animation.
        """
        self._next_update = monotonic_ns() + self._time_left_at_pause
        self._time_left_at_pause = 0
        self._paused = False

    def fill(self, color):
        """
        Fills the pixel object with a color.
        """
        self.pixel_object.fill(color)

    @property
    def color(self):
        """
        The current color.
        """
        return self._color

    @color.setter
    def color(self, color):
        if self._color == color:
            return
        if isinstance(color, int):
            color = (color >> 16 & 0xFF, color >> 8 & 0xFF, color & 0xFF)
        self._color = color
        self._recompute_color(color)

    @property
    def speed(self):
        """
        The animation speed in fractional seconds.
        """
        return self._speed_ns / NANOS_PER_SECOND

    @speed.setter
    def speed(self, seconds):
        self._speed_ns = int(seconds * NANOS_PER_SECOND)

    def _recompute_color(self, color):
        """
        Called if the color is changed, which includes at initialization.
        Override as needed.
        """

    def cycle_complete(self):
        """
        Called by some animations when they complete an animation cycle.
        Animations that support cycle complete notifications will have X property set to False.
        Override as needed.
        """
        self.cycle_count += 1
        if self.cycle_count % self.notify_cycles == 0:
            for callback in self._also_notify:
                callback(self)

    def add_cycle_complete_receiver(self, callback):
        """
        Adds an additional callback when the cycle completes.

        :param callback: Additional callback to trigger when a cycle completes.  The callback
                         is passed the animation object instance.
        """
        self._also_notify.append(callback)

    def reset(self):
        """
        Resets the animation sequence.
        """


class ColorCycle(Animation):
    """
    Animate a sequence of one or more colors, cycling at the specified speed.

    :param pixel_object: The initialised LED object.
    :param float speed: Animation speed in seconds, e.g. ``0.1``.
    :param colors: A list of colors to cycle through in ``(r, g, b)`` tuple, or ``0x000000`` hex
                   format. Defaults to a rainbow color cycle.
    """

    def __init__(self, pixel_object, speed, colors=RAINBOW, name=None):
        self.colors = colors
        super().__init__(pixel_object, speed, colors[0], name=name)
        self._generator = self._color_generator()
        next(self._generator)

    cycle_complete_supported = True

    def draw(self):
        self.pixel_object.fill(self.color)
        self.show()
        next(self._generator)

    def _color_generator(self):
        index = 0
        while True:
            self._color = self.colors[index]
            yield
            index = (index + 1) % len(self.colors)
            if index == 0:
                self.cycle_complete()

    def reset(self):
        """
        Resets to the first color.
        """
        self._generator = self._color_generator()


class Blink(ColorCycle):
    """
    Blink a color on and off.

    :param pixel_object: The initialised LED object.
    :param float speed: Animation speed in seconds, e.g. ``0.1``.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    """

    def __init__(self, pixel_object, speed, color, name=None):
        super().__init__(pixel_object, speed, [color, BLACK], name=name)

    def _recompute_color(self, color):
        self.colors = [color, BLACK]


class Solid(ColorCycle):
    """
    A solid color.

    :param pixel_object: The initialised LED object.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    """

    def __init__(self, pixel_object, color, name=None):
        super().__init__(pixel_object, speed=1, colors=[color], name=name)

    def _recompute_color(self, color):
        self.colors = [color]


class Comet(Animation):
    """
    A comet animation.

    :param pixel_object: The initialised LED object.
    :param float speed: Animation speed in seconds, e.g. ``0.1``.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    :param int tail_length: The length of the comet. Defaults to 10. Cannot exceed the number of
                            pixels present in the pixel object, e.g. if the strip is 30 pixels
                            long, the ``tail_length`` cannot exceed 30 pixels.
    :param bool reverse: Animates the comet in the reverse order. Defaults to ``False``.
    :param bool bounce: Comet will bounce back and forth. Defaults to ``True``.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        pixel_object,
        speed,
        color,
        tail_length=10,
        reverse=False,
        bounce=False,
        name=None,
    ):
        self._tail_length = tail_length + 1
        self._color_step = 0.9 / tail_length
        self._color_offset = 0.1
        self._comet_colors = None
        self._reverse_comet_colors = None
        self._initial_reverse = reverse
        self.reverse = reverse
        self.bounce = bounce
        self._computed_color = color
        self._generator = self._comet_generator()
        super().__init__(pixel_object, speed, color, name=name)

    cycle_complete_supported = True

    def _recompute_color(self, color):
        pass

    def __recompute_color(self, color):
        self._comet_colors = [BLACK] + [
            [
                int(color[rgb] * ((n * self._color_step) + self._color_offset))
                for rgb in range(len(color))
            ]
            for n in range(self._tail_length - 1)
        ]
        self._reverse_comet_colors = list(reversed(self._comet_colors))
        self._computed_color = color

    def _get_range(self, num_pixels):
        if self.reverse:
            return range(num_pixels, -self._tail_length - 1, -1)
        return range(-self._tail_length, num_pixels + 1)

    def _comet_generator(self):
        num_pixels = len(self.pixel_object)
        cycle_passes = 0
        while True:
            if self._color != self._computed_color or not self._comet_colors:
                self.__recompute_color(self._color)
            colors = self._reverse_comet_colors if self.reverse else self._comet_colors
            for start in self._get_range(num_pixels):

                if start + self._tail_length < num_pixels:
                    end = self._tail_length
                else:
                    end = num_pixels - start
                if start <= 0:
                    num_visible = self._tail_length + start
                    self.pixel_object[0:num_visible] = colors[
                        self._tail_length - num_visible :
                    ]
                else:
                    self.pixel_object[start : start + end] = colors[0:end]
                self.show()
                yield
            cycle_passes += 1
            if self.bounce:
                self.reverse = not self.reverse
            if not self.bounce or cycle_passes == 2:
                self.cycle_complete()
                cycle_passes = 0

    def draw(self):
        next(self._generator)

    def reset(self):
        """
        Resets to the first color.
        """
        self._generator = self._comet_generator()
        self.reverse = self._initial_reverse


class Pulse(Animation):
    """
    Pulse all pixels a single color.

    :param pixel_object: The initialised LED object.
    :param float speed: Animation refresh rate in seconds, e.g. ``0.1``.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    :param period: Period to pulse the LEDs over.  Default 5.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, pixel_object, speed, color, period=5, name=None):
        super().__init__(pixel_object, speed, color, name=name)
        self._period = period
        self._generator = None
        self.reset()

    cycle_complete_supported = True

    def draw(self):
        color = next(self._generator)
        self.fill(color)
        self.show()

    def reset(self):
        """
        Resets the animation.
        """
        white = len(self.pixel_object[0]) > 3 and isinstance(
            self.pixel_object[0][-1], int
        )
        from adafruit_led_animation.helper import (  # pylint: disable=import-outside-toplevel
            pulse_generator,
        )

        self._generator = pulse_generator(self._period, self, white)


class Chase(Animation):
    """
    Chase pixels in one direction in a single color, like a theater marquee sign.

    :param pixel_object: The initialised LED object.
    :param float speed: Animation speed rate in seconds, e.g. ``0.1``.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    :param size: Number of pixels to turn on in a row.
    :param spacing: Number of pixels to turn off in a row.
    :param reverse: Reverse direction of movement.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self, pixel_object, speed, color, size=2, spacing=3, reverse=False, name=None
    ):
        self._size = size
        self._spacing = spacing
        self._repeat_width = size + spacing
        self._num_repeats = ceil(len(pixel_object) / self._repeat_width)
        self._overflow = len(pixel_object) % self._repeat_width
        self._direction = 1 if not reverse else -1
        self._reverse = reverse
        self._offset = 0

        def _resetter():
            self._offset = 0
            self._reverse = reverse
            self._direction = 1 if not reverse else -1

        self._reset = _resetter

        super().__init__(pixel_object, speed, color, name=name)

    cycle_complete_supported = True

    @property
    def reverse(self):
        """
        Whether the animation is reversed
        """
        return self._reverse

    @reverse.setter
    def reverse(self, value):
        self._reverse = value
        self._direction = -1 if self._reverse else 1

    def draw(self):
        def bar_colors():
            bar_no = 0
            for i in range(self._offset, 0, -1):
                if i > self._spacing:
                    yield self.bar_color(bar_no, i)
                else:
                    yield self.space_color(bar_no, i)
                    bar_no = 1
            while True:
                for bar_pixel in range(self._size):
                    yield self.bar_color(bar_no, bar_pixel)
                for space_pixel in range(self._spacing):
                    yield self.space_color(bar_no, space_pixel)
                bar_no += 1

        colorgen = bar_colors()
        self.pixel_object[:] = [next(colorgen) for _ in self.pixel_object]
        self.show()

        if self.draw_count % len(self.pixel_object) == 0:
            self.cycle_complete()
        self._offset = (self._offset + self._direction) % self._repeat_width

    def bar_color(self, n, pixel_no=0):  # pylint: disable=unused-argument
        """
        Generate the color for the n'th bar_color in the Chase

        :param n: The pixel group to get the color for
        :param pixel_no: Which pixel in the group to get the color for
        """
        return self.color

    def space_color(self, n, pixel_no=0):  # pylint: disable=unused-argument,no-self-use
        """
        Generate the spacing color for the n'th bar_color in the Chase

        :param n: The pixel group to get the spacing color for
        :param pixel_no: Which pixel in the group to get the spacing color for
        """
        return 0

    def reset(self):
        """
        Reset the animation.
        """
        self._reset()
