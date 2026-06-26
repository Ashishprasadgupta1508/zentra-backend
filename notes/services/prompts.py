MODULE_PROMPT = """
You are an expert AI teacher.

Analyze the following study material.

Generate JSON only.

Rules:

1. Detect Subject
2. Write Short Summary
3. Divide into Modules
4. Each Module should contain Topics

Return only JSON.

Format:

{
  "subject":"",

  "summary":"",

  "modules":[

      {

          "title":"",

          "topics":[
              "",
              "",
              ""
          ]

      }

  ]

}

Study Material:

"""