&#8226; [Home](index.md) &#8226; Sentences

# Template Language

Voice commands are recognized by `voice2json` from a set of **template sentences** that you define in your [profile](profiles.md). These are stored in an [ini file](https://docs.python.org/3/library/configparser.html) (`sentences.ini`) whose  section values are simplified [JSGF grammars](https://www.w3.org/TR/jsgf/). The set of all sentences *represented* in these grammars is used to create an [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) and an intent recognizer. See [the whitepaper](whitepaper.md) for details.

## Motivation

The combination of an ini file and JSGF is arguably an abuse of *two* file formats, so why do this? At a minimum, `voice2json` needs a set of sentences, grouped by intent, in order to train the speech and intent recognizers. A fairly pleasant way to express this in text (I think) is as follows:

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

Within a sentence, you can specify optional word(s) by surrounding them `[with brackets]`. These represents at least two sentences: one with the optional word(s), and one without. So the following sentence template:

```
[an] example sentence [with] some optional words
```

represents 4 concrete sentences:

1. `an example sentence with some optional words`
2. `example sentence with some optional words`
3. `an example sentence some optional words`
4. `example sentence some optional words`

## Alternatives

A set of items, where only one is present at a time, is `(specified | like | this)`. For N alternatives, there will be N different sentences represented (unless you nest optional words, etc.). The template:

```
set the light to (red | green | blue)
```

will represent:

1. `set the light to red`
2. `set the light to green`
3. `set the light to blue`

## Rules

Rules allow you to reuse common phrases, alternatives, etc. Rules are defined by `rule_name = ...` alongside your sentences and referenced by `<rule_name>`. The template above with colors could be rewritten as:

```
colors = (red | green | blue)
set the light to <colors>
```

which will represent the same 4 sentences as above. Importantly, you can **share rules** across intents by prefixing the rule's name with the intent name followed by a dot:

```
[SetLightColor]
colors = (red | green | blue)
set the light to <colors>

[GetLightColor]
is the light <SetLightColor.colors>
```

The second intent (`GetLightColor`) references the `colors` rule from `SetLightColor`.

## Tags

The example templates above represent sentences for training the speech recognizer, but using them as-is to train the *intent recognizer* will not be satisfactory. The **color** in the `SetLightColor` intent, for example, is obviously important for a system that will fulfill it (i.e., *actually* change a light's color). `voice2json`'s intent recognizer just needs a little extra information from you, the user.

Luckily, JSGF has a [tag feature](https://www.w3.org/TR/jsgf/#15057) that lets you annotate portions of sentences/rules. `voice2json` interprets that the JSGF tag text (**inside** `{...}`) as *slot/entity names* and the tagged portions of the sentence (**left of** `{...}`) as *slot/entity values*. The `SetLightColor` example can be extended with tags like this:

```
[SetLightColor]
colors = (red | green | blue){color}
set the light to <colors>
```

With the `{color}` tag attached to the `(red | green | blue)` alternative set, each color name will carry the tag. This is the same as typing `((red){color} | (green){color} | (blue){color})`, but less verbose. This template now represents the following **tagged sentences**:

1. `set the light to [red](color)`
2. `set the light to [green](color)`
3. `set the light to [blue](color)`

When the `SetLightColor` intent is recognized now, perhaps with "set the light to red", the corresponding [JSON event](formats.md#intents) will have a `color` entity/slot with the value of `red`:

```json
{
    "intent": {
        "name": "SetColor"
    },
    "entities": [
        { "entity": "color", "value": "red" }
    ],
    "slots": {
        "color": "red"
    }
}
```

The downstream system that will use this event to fulfill the user's intent (e.g., [Node-RED](https://nodered.org)) now only has to inspect the `color` slot to decide what to do! 

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

The syntax `on:enable` tells `voice2json` to *listen* for the word `on`, but *emit* the word `enable` in its place. Similarly, the syntax `(living room lamp){name:switch_1}` tells `voice2json` to listen for `living room lamp`, but *actually* put `switch_1` in the `name` slot:

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

This will *only* match the spoken commands `turn on a red light` and `turn on an orange light`, and the `color` slot will never contain "a" or "an"!

### Extra Words

You can also use substitution to add words that are not present in the speech:

```
[LightState]
:please turn on the light
```

will accept the spoken sentence "turn on the light", but emit "please turn on the light" in the recognized intent.


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
This is possible in `voice2json` by placing text files in the directory given in `training.slots-directory` from your [profile](profiles.md) (`slots/` by default).

By putting the movie names above in a text file at `slots/movies`...

```
Primer
Moon
Chronicle
Timecrimes
Coherence
```

you can now reference them as `$movies` in your your `sentences.ini` file! Something like:

```
[PlayMovie]
play ($movies){movie_name}
```

will generate JSON events like:

```json
{
    "intent": {
        "name": "PlayMovie"
    },
    "entities": [
        { "entity": "movie_name", "value": "Primer" }
    ]
    "slots": {
        "movie_name": "Primer"
    }
}
```

If you update the `movies` file, make sure to [re-train `voice2json`](commands.md#train-profile) in order to pick up the new movie names. Only intent grammars that reference `$movies` will be re-built.

## Number Replacement

For most of the supported languages, `voice2json` can automaticaly replace numbers (e.g., "75") with words ("seventy five"). If you have `training.replace-numbers` set to `true` in [your profile](profiles.md), you can freely include numbers in your sentences. Through [substitution](#wordtag-substitutions), the original numbers will show up in your recognized intent.

For example:

```
[SetTemperature]
set the temperature to 75
```

will be translated to:

```
[SetTemperature]
set the temperature to seventy: five:75
```

During [intent recognition](commands.md#recognize-intent), "seventy five" will be replaced with "75".

## Escaping

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

The following features from the [full JSGF specification](https://www.w3.org/TR/jsgf/) are not supported in `voice2json`:

* Plus Operator (`+`)
* Kleene Star (`*`)
* Weights (`/10/`)
* Recursion
* `<NULL>` and `<VOID>`
* Documentation comments (`/**`)
    * Just use ini-style comments instead (`#`)
