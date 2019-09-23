# Voice Command Language

Voice commands are recognized by voice2json from a set of sentences that you define in your [profile](profiles.md). These are stored in an [ini file](https://docs.python.org/3/library/configparser.html) whose "values" are simplified [JSGF grammars](https://www.w3.org/TR/jsgf/). The set of all sentences *represented* in these grammars is used to create an [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) and an intent recognizer.

### Motivation

The combination of an ini file and JSGF is arguably an abuse of two file formats, so why do this? At a minimum, voice2json needs a set of sentences, grouped by intent, in order to train the speech and intent recognizers. A fairly pleasant way to express this in text is as follows:

    [Intent 1]
    sentence 1
    sentence 2
    ...

    [Intent 2]
    sentence 3
    sentence 4
    ...

Compared to JSON, YAML, etc., there is minimal syntactic overhead for the purposes of **just writing down sentences**. However, its *shortcomings* become painfully obvious once you have more than a handful of sentences or intents:

1. If two sentences are nearly identical, save for an *optional word* like "the" or "a", you have to maintain two nearly identical copies of a sentence.
2. When speaking about collections of things, like colors or states (on/off), you need a sentence for every *alternative choice*.
3. You cannot share commonly *repeated phrases* across sentences or intents.
4. There is no way to *annotate phrases* so the intent recognizer knows the values for an intent's **named entities/slots** (e.g., color).

Each of these shortcomings are addressed by considering the space between intent headings (`[Intent 1]`, etc.) as a **grammar** that will represent a space of valid, annotated voice commands. `voice2json` specifically represents these spaces as [finite state transducers](http://www.openfst.org), serving as input to [opengrm](https://www.opengrm.org) to produce language models **without ever generating a single sentence**. The same representation is then used to [recognize intents](commands.md#recognize-text).

### Optional Words

Within a sentence, you can specify optional word(s) by surrounding them `[with brackets]`. These will generate at least two sentences: one with the optional word(s), and one without. So the following sentence template:

    [an] example sentence [with] some optional words

will generate 4 concrete sentences:

1. `an example sentence with some optional words`
2. `example sentence with some optional words`
3. `an example sentence some optional words`
4. `example sentence some optional words`

### Alternatives

A set of items, where only one is present at a time, is `(specified | like | this)`. For N items, there will be N sentences generated (unless you nest optional words, etc.). The template:

    set the light to (red | green | blue)

will generate:

1. `set the light to red`
2. `set the light to green`
3. `set the light to blue`

### Rules

Rules allow you to reuse common phrases, alternatives, etc. Rules are defined by `rule_name = ...` alongside your sentences and referenced by `<rule_name>`. The template above with colors could be rewritten as:

    colors = (red | green | blue)
    set the light to <colors>

which will generate the same 4 sentences as above. Importantly, you can **share rules** across intents by prefixing the rule's name with the intent name followed by a dot:

    [SetLightColor]
    colors = (red | green | blue)
    set the light to <colors>

    [GetLightColor]
    is the light <SetLightColor.colors>

The second intent (`GetLightColor`) references the `colors` rule from `SetLightColor`.

### Tags

The example templates above will generate sentences for training the speech recognizer, but using them to train the intent recognizer will not be satisfactory. The `SetLightColor` intent, when recognized, will result in a Home Assistant event called `rhasspy_SetLightColor`. But the actual *color* will not be provided because the intent recognizer is not aware that a `color` slot should exist (and has the values `red`, `green`, and `blue`).

Luckily, JSGF has a [tag feature](https://www.w3.org/TR/jsgf/#15057) that lets you annotate portions of sentences/rules. `voice2json` assumes that the tags themselves are *slot/entity names* and the tagged portions of the sentence are *slot/entity values*. The `SetLightColor` example can be extended with tags like this:

    [SetLightColor]
    colors = (red | green | blue){color}
    set the light to <colors>

With the `{color}` tag attached to the `(red | green | blue)` alternative set, each color name will carry the tag. This is the same as typing `((red){color} | (green){color} | (blue){color})`, but less verbose. `voice2json` will now generate the following **tagged sentences**:

1. `set the light to [red](color)`
2. `set the light to [green](color)`
3. `set the light to [blue](color)`

When the `SetLightColor` intent is recognized now, the corresponding JSON event (`rhasspy_SetLightColor` in Home Assistant) will have the following properties:

    {
      "color": "red"
    }


A Home Assistant [automation](https://www.home-assistant.io/docs/automation) can use the slot values to take an appropriate action, such as [setting an RGB light's color](https://www.home-assistant.io/docs/automation/action/) to `[255,0,0]` (red).

#### Tag Synonyms

There are times where you want to match a particular part of your sentence with a tag, but want the actual *value* of the tag to be something different than the matched text. This is needed if you want to talk about entities in Home Assistant, for example, with phrases like "the living room lamp", but want to pass the appropriate entity id (say `lamp_1`) to Home Assistant instead.

Normally, you would tag part of a sentence like this:

    [ChangeLightState]
    turn on the (living room lamp){name}

When this intent is activated, `voice2json` will send a JSON event (named `rhasspy_ChangeLightState` in Home Assistant) with:

    {
      "name": "living room lamp"
    }

You can catch this event in a Home Assistant automation, match the `name` "living room name", and do something with the `lamp_1` entity. That's fine for one instance, but would require a separate rule for every `name`! Instead, let's add a tag **synonym**:

    [ChangeLightState]
    turn on the (living room lamp){name:lamp_1}

The tag label and synonym are separated by a ":". When this sentence is spoken and the intent is activated, the same `rhasspy_ChangeLightState` event will be sent to Home Assistant, but with the following data:

    {
      "name": "lamp_1"
    }

Now in your Home Assistant automation, you could use [templating](https://www.home-assistant.io/docs/automation/templating/) to plug the `name` directly into the `entity_id` field of an action. One rule to rule them all.

This same technique could be used to replace number words with digits, like:

    [SetTimer]
    set a timer for (ten){number:10} seconds

which would generate an event like this when recognized:

    {
      "number": "10"
    }

### Slots Lists

In the `SetLightColor` example above, the color names are stored in `sentences.ini` as a rule:

    colors = (red | green | blue)

Ths is convenient when the list of colors is small, changes infrequently, and does not depend on an external service.
But what if this was a list of movie names that were stored on your [Kodi Home Theater](https://kodi.tv)?

    movies = ("Primer" | "Moon" | "Chronicle" | "Timecrimes" | "Mulholland Drive" | ... )

It would be much easier if this list was stored externally, but could be *referenced* in the appropriate places in the grammar.
This is possible in `voice2json` by placing text files in the `speech_to_text.slots_dir` directory specified in your [profile](profiles.md) ("slots" by default).

If you're using the English (`en`) profile, for example, create the file `profiles/en/slots/movies` and add the following content:

    Primer
    Moon
    Chronicle
    Timecrimes
    Mullholand Drive

This list of movie can now be referenced as `$movies` in your your `sentences.ini` file! Something like:

    [PlayMovie]
    play ($movies){movie_name}

will generate `rhasspy_PlayMovie` events like:

    {
      "movie_name": "Primer"
    }

If you update the `movies` file, make sure to re-train `voice2json` in order to pick up the new movie names.

### Special Cases

If one of your sentences happens to start with an optional word (e.g., `[the]`), this can lead to a problem:

    [SomeIntent]
    [the] problem sentence

Python's [configparser](https://docs.python.org/3/library/configparser.html) will interpret `[the]` as a new section header, which will produce a new intent, grammar, etc. `voice2json` handles this special case by using a backslash escape sequence (`\[`):

    [SomeIntent]
    \[the] problem sentence

Now `[the]` will be properly interpreted as a sentence under `[SomeIntent]`. You only need to escape a `[` if it's the **very first** character in your sentence.
