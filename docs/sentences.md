# Voice Command Language

Voice commands are recognized by voice2json from a set of sentences that you define in your [profile](profiles.md). These are stored in an [ini file](https://docs.python.org/3/library/configparser.html) whose "values" are simplified [JSGF grammars](https://www.w3.org/TR/jsgf/). The set of all sentences *represented* in these grammars is used to create an [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) and an intent recognizer.

## Motivation

The combination of an ini file and JSGF is arguably an abuse of two file formats, so why do this? At a minimum, voice2json needs a set of sentences, grouped by intent, in order to train the speech and intent recognizers. A fairly pleasant way to express this in text is as follows:

```
[Intent 1]
sentence 1
sentence 2
...

[Intent 2]
sentence 3
sentence 4
...
```

Compared to JSON, YAML, etc., there is minimal syntactic overhead for the purposes of **just writing down sentences**. However, its *shortcomings* become painfully obvious once you have more than a handful of sentences or intents:

1. If two sentences are nearly identical, save for an *optional word* like "the" or "a", you have to maintain two nearly identical copies of a sentence.
2. When speaking about collections of things, like colors or states (on/off), you need a sentence for every *alternative choice*.
3. You cannot share commonly *repeated phrases* across sentences or intents.
4. There is no way to *annotate phrases* so the intent recognizer knows the values for an intent's **named entities/slots** (e.g., color).

Each of these shortcomings are addressed by considering the space between intent headings (`[Intent 1]`, etc.) as a **grammar** that will represent a space of valid, annotated voice commands. `voice2json` specifically represents these spaces as [finite state transducers](http://www.openfst.org), serving as input to [opengrm](https://www.opengrm.org) to produce language models **without ever generating a single sentence**. The same representation is then used to [recognize intents](commands.md#recognize-intent).

## Optional Words

Within a sentence, you can specify optional word(s) by surrounding them `[with brackets]`. These will generate at least two sentences: one with the optional word(s), and one without. So the following sentence template:

```
[an] example sentence [with] some optional words
```

will generate 4 concrete sentences:

1. `an example sentence with some optional words`
2. `example sentence with some optional words`
3. `an example sentence some optional words`
4. `example sentence some optional words`

## Alternatives

A set of items, where only one is present at a time, is `(specified | like | this)`. For N items, there will be N sentences generated (unless you nest optional words, etc.). The template:

```
set the light to (red | green | blue)
```

will generate:

1. `set the light to red`
2. `set the light to green`
3. `set the light to blue`

## Rules

Rules allow you to reuse common phrases, alternatives, etc. Rules are defined by `rule_name = ...` alongside your sentences and referenced by `<rule_name>`. The template above with colors could be rewritten as:

```
colors = (red | green | blue)
set the light to <colors>
```

which will generate the same 4 sentences as above. Importantly, you can **share rules** across intents by prefixing the rule's name with the intent name followed by a dot:

```
[SetLightColor]
colors = (red | green | blue)
set the light to <colors>

[GetLightColor]
is the light <SetLightColor.colors>
```

The second intent (`GetLightColor`) references the `colors` rule from `SetLightColor`.

## Word/Tag Substitutions

`voice2json` allows you to control how words are emitted in the final [JSON event](formats.md#intents).

Consider the following example with two lights, a lamp in the living room and a light in the garage:

```
[LightState]
state = (on | off)
name = (living room lamp | garage light)
turn (<state>){state} [the] (<name>){name}
```

If the voice command "turn on the living room lamp" is spoken, `voice2json` will produce the expected JSON:

```json
{ 
  "intent": {
    "name": "LightState"
  },
  "slots": {
    "state": "on",
    "name": "living room lamp"
  }
}
```

If the system that **consumes** this JSON does not know what `on` and `living room lamp` are, however, it will be unable to handle the intent. Suppose this hypothetical system knows only how to `enable` and `disable` either `switch_1` or `switch_2`. We could ease the burden of interfacing with some minor modifications to `sentences.ini`:

```
[LightState]
state = (on:enable | off:disable)
name = (living room lamp){name:switch_1} | (garage light){name:switch_2}
turn (<state>){state} [the] (<name>)
```

The syntax `on:enable` tells `voice2json` to *listen* for the word `on`, but *emit* the word `enable` in its place. Similarly, the syntax `(living room lamp){name:switch_1}` tells `voice2json` to listen for `living room lamp`, but *actually put* `switch_1` in the `name` slot:

```json
{
  "text": "turn enable the switch_1",
  "intent": {
    "name": "LightState",
    "confidence": 1
  },
  "entities": [
    {
      "entity": "state",
      "value": "enable",
      "raw_value": "on",
      "start": 5,
      "raw_start": 5,
      "end": 11,
      "raw_end": 7
    },
    {
      "entity": "name",
      "value": "switch_1",
      "raw_value": "living room lamp",
      "start": 16,
      "raw_start": 12,
      "end": 24,
      "raw_end": 28
    }
  ],
  "raw_text": "turn on the living room lamp",
  "tokens": [
    "turn",
    "enable",
    "the",
    "switch_1"
  ],
  "raw_tokens": [
    "turn",
    "on",
    "the",
    "living",
    "room",
    "lamp"
  ],
  "slots": {
    "state": "enable",
    "name": "switch_1"
  },
  "intents": [],
  "recognize_seconds": 0.000274658203125
}
```

Notice that with substitutions, the `text` and `raw_text` properties of the recognized intent no longer match. Likewise, `raw_value` differs from `value` for each entity. The `raw_` properties contain the left side of the `:` in each substitution.

### Slot Substitutions

This syntax also works **inside slot files**. When nothing is put on the right side of the `:`, the word is silently dropped, so:

```
[the:] light
```

will match both `the light` and `light`, but always emit just `light`. This technique is especially useful in English with articles like "a" and "an". It is common to write something in `sentences.ini` like this:

```
[LightState]
turn on (a | an) ($colors){color} light
```

where `slots/colors` might be:

```
red
orange
```

This will match `turn on a red light` and `turn on an orange light` as intended, but also `turn on an red light` and `turn on a orange light`. Using word replacement and a slot file, we can instead write:

```
[LightState]
turn on ($colors){color} light
```

where `slots/colors` is:

```
a: red
an: orange
```

This will *only* match `turn on a red light` and `turn on an orange light` as well as ensuring that the `color` slot does not contain "a" or "an"!

### Extra Words

You can also use substitution to add words that are not present in the speech:

```
[LightState]
:please turn on the light
```

will accept the spoken sentence "turn on the light", but emit "please turn on the light" in the recognized intent.

## Tags

The example templates above will generate sentences for training the speech recognizer, but using them to train the intent recognizer will not be satisfactory. The `SetLightColor` intent, when recognized, will result in a Home Assistant event called `rhasspy_SetLightColor`. But the actual *color* will not be provided because the intent recognizer is not aware that a `color` slot should exist (and has the values `red`, `green`, and `blue`).

Luckily, JSGF has a [tag feature](https://www.w3.org/TR/jsgf/#15057) that lets you annotate portions of sentences/rules. ``voice2json`` assumes that the tags themselves are *slot/entity names* and the tagged portions of the sentence are *slot/entity values*. The `SetLightColor` example can be extended with tags like this:

```
[SetLightColor]
colors = (red | green | blue){color}
set the light to <colors>
```

With the `{color}` tag attached to the `(red | green | blue)` alternative set, each color name will carry the tag. This is the same as typing `((red){color} | (green){color} | (blue){color})`, but less verbose. `voice2json` will now generate the following **tagged sentences**:

1. `set the light to [red](color)`
2. `set the light to [green](color)`
3. `set the light to [blue](color)`

When the `SetLightColor` intent is recognized now, the corresponding JSON event (`rhasspy_SetLightColor` in Home Assistant) will have the following properties:

```json
{
  "color": "red"
}
```

A Home Assistant [automation](https://www.home-assistant.io/docs/automation) can use the slot values to take an appropriate action, such as [setting an RGB light's color](https://www.home-assistant.io/docs/automation/action/) to `[255,0,0]` (red).


## Slot References

In the `SetLightColor` example above, the color names are stored in `sentences.ini` as a rule:

```
colors = (red | green | blue)
```

Ths is convenient when the list of colors is small, changes infrequently, and does not depend on an external service.
But what if this was a list of movie names that were stored on your [Kodi Home Theater](https://kodi.tv)?

```
movies = ("Primer" | "Moon" | "Chronicle" | "Timecrimes" | "Coherence" | ... )
```

It would be much easier if this list was stored externally, but could be *referenced* in the appropriate places in the grammar.
This is possible in `voice2json` by placing text files in the `speech_to_text.slots_dir` directory specified in your [profile](profiles.md) ("slots" by default).

If you're using the English (`en`) profile, for example, create the file `profiles/en/slots/movies` and add the following content:

```
Primer
Moon
Chronicle
Timecrimes
Coherence
```

This list of movie can now be referenced as `$movies` in your your `sentences.ini` file! Something like:

```
[PlayMovie]
play ($movies){movie_name}
```

will generate `rhasspy_PlayMovie` events like:

```json
{
  "movie_name": "Primer"
}
```

If you update the `movies` file, make sure to re-train `voice2json` in order to pick up the new movie names.

## Special Cases

If one of your sentences happens to start with an optional word (e.g., `[the]`), this can lead to a problem:

```
[SomeIntent]
[the] problem sentence
```

Python's [configparser](https://docs.python.org/3/library/configparser.html) will interpret `[the]` as a new section header, which will produce a new intent, grammar, etc. `voice2json` handles this special case by using a backslash escape sequence (`\[`):

```
[SomeIntent]
\[the] problem sentence
```

Now `[the]` will be properly interpreted as a sentence under `[SomeIntent]`. You only need to escape a `[` if it's the **very first** character in your sentence.

## Missing JSGF Features

* Plus Operator
* Kleene Star
* Weights
