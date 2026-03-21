# Schema Guide

## Why?

Even though it’s not strictly required, defining your configuration using a YAML
schema allows it to be automatically validated using **Pydantic** under the hood.

This ensures that everything passed to your Python classes matches the expected
types, helping you avoid subtle bugs.

This is useful to be sure 100% that the things passed to your python classes be exactly what you expect
and not waste time on some regression error cause you pass a string to something else.

Moreover it serves as a sort of documentation of your config that is your single source of truth of instantiated objects and cabled values,
to help people that work together to understand easily where all the values are and what are their scope.
