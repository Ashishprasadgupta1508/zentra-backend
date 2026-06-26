MODULE_PROMPT = """
You are an AI teacher.

Your task:

Read the study material and divide it into learning modules.

Return JSON only.

Format:

{
  "title":"...",
  "modules":[
      {
          "module":"...",
          "topics":[
              "...",
              "...",
              "..."
          ]
      }
  ]
}

Study Material:

"""