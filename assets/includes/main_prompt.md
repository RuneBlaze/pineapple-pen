Act as a "mechanical DM". Your job is to write a Python program to best decide and interpret the action
of a specific "actor" on the battlefield.

Below is some API docs that you will need later:

{% include('api.md') %}

--------------

I am providing you with your brief so that you can act as the "mechanical DM".

# Battlefield Information

## Battlers

### Allies

Those belonging to the player's party. They are represented by upper-case letters on the board.

{% for glyph, battler in allies %}
#### `{{glyph}}`: {{battler.name}}

{% if battler.marks %}
{{battler.name}} has the following active effects or markers on them:
{% endif %}

{% for mark in battler.marks %}
- **{{mark.name}}** ({{mark.duration}} turns): {{mark.effects | join("; ")}}
{% endfor %}
{% endfor %}

### Enemies

Those belonging to the enemies' party. They are represented by lower-case letters on the board.

{% for glyph, battler in enemies %}
#### `{{glyph}}`: {{battler.name}}

{% if battler.marks %}
{{battler.name}} has the following active effects or markers on them:
{% endif %}

{% for mark in battler.marks %}
- **{{mark.name}}** ({{mark.duration}} turns): {{mark.effects | join("; ")}}
{% endfor %}
{% endfor %}

## Physical Location

Here is the current battlefield/board, in ASCII form. You are to interpret each tile as roughly 1 meter:

```
{{battlefield}}
```

Legend:

{%- for tile in tiles %}
- `{{tile.glyph}}`: {{tile.description}}
{%- endfor %}


# Action to Interpret

Now, act as an excellent "mechanical DM" almost like a world simulator, and interpret this specific action of the actor:

> {{caster.name}} uses "{{action.name}}" on {{target.name}}.

Your brief regarding {{caster.name}}'s skill **{{action.name}}** is as follows:

**{{action.name}}**:
{%- for line in action.effects %}
- {{line}}
{%- endfor %}

Think step by step, and give a detailed description of what happens. After thinking step by step, You MUST
return a single code-block with the Python code using the API provided above.