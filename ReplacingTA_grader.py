import os
import shutil
from typing import Dict, List
import pandas as pd
import llm

################################################################
# Import the EvaDB package
import evadb
# Connect to EvaDB and get a database cursor for running queries
import warnings
warnings.filterwarnings("ignore")
################################################################

NEW_RUBRIC_PATH = os.path.join("evadb_data", "tmp", "new_rubric.csv")


# def try_to_import_llm():
#     """
#     Check the llm package
#     """
#     try:
#         import llm
#     except ImportError:
#         raise ValueError(
#             """
#             Could not import llm python package.
#             Please install it with 'pip install -r requirements.txt'.
#             """
#         )

def cleanup():
    """Removes any temporary file / directory created by EvaDB."""
    if os.path.exists("evadb_data"):
        shutil.rmtree("evadb_data")

def handle_user_input() -> Dict:
    """
    Receives user input.

    Returns:
        user_input (dict): global configuration
    """

    print(
        "Welcome to GRADER, This app is going to grade your answer based on your/generated rubric \n \
        You will need the 'Problem' and 'Answer' you want to score.\n"
    )

    question_str = str(
        input(
            "Provide 'Question' here :: "
        )
    )

    question_str = question_str.replace("\"", "")

    answer_str = str(
        input(
            "Provide 'Answer' you want to grade here :: "
        )
    )

    


    use_rubric_pdf = None
    while True:
        if use_rubric_pdf in ["y", 'yes']:
            use_rubric = True
            break
        elif use_rubric_pdf in ["n", "no"]:
            use_rubric = False
            break
        else:
            use_rubric_pdf = str(
                input(
                    "Do you have a rubric for this question? ('yes' for using your rubric / 'no' for using automatic generated rubric) ::"
                ).lower()
            )

    
    user_input = {'question' : question_str,
                  'answer' : answer_str,
                  'use_rubric' : use_rubric} # str, str, bool
    
    return user_input



def get_rubric_pdf():

    current_directory = os.getcwd()
    rubric_pdf_local_path = str(
        input(
            "Enter the local path to your rubric pdf ::"
        )
    )
    
    rubric_name = os.path.basename(rubric_pdf_local_path)
    user_input['rubric_pdf_name'] = rubric_name

    check_file_here = os.path.join(current_directory, rubric_name)

    if os.path.exists(check_file_here):
        print("✅ Your Rubric is alread in this current directory!")
    else:
        print("Moving your file into current directory...")
        try:
            shutil.move(rubric_pdf_local_path, current_directory)
            print(f"✅ Rubric moved successfully from '{rubric_pdf_local_path}' to '{current_directory}'")
        except FileNotFoundError:
            print("Source file not found.")
        except PermissionError:
            print("Permission denied. Make sure you have the necessary permissions to move the file.")
        except Exception as e:
            print(f"An error occurred: {e}")
    print(user_input)
    cursor.query("DROP TABLE IF EXISTS Rubric_PDF;").df()
    cursor.query("LOAD PDF '{}' INTO Rubric_PDF;".format(user_input['rubric_pdf_name'])).df()
    # print(cursor.query("SELECT * FROM Rubric_PDF").df())
    return

def generate_rubric():
    # llm 이용 promt(..., system="~") -> get rubric -> store them into table

    rubric_no_request = int(
        input(
            "How many rubrics you need? (only integer) :: "
        )
    )

    total_score_request = int(
        input(
            "What is the total score is this question? (only integer) :: "
        )
    )

    PROMPT_RUBRIC = '''
                    Give me {rubrics_no} grading rubrics for total {total_score} points for below question:
                    "{question}"
                    And, your rubrics should fit in this json format:
                    [{{
                        point_type: "+",
                        point_value: value of point,
                        explanation: in one string sentence
                    }}]
                    '''.format(rubrics_no = rubric_no_request,
                               total_score = total_score_request,
                               question = user_input["question"])
    print(PROMPT_RUBRIC)
    response = model.prompt(PROMPT_RUBRIC,
                            system="Answer like your Teaching Assistant", temperature=0.5)
    
    print(response)




def split_string(text):
    parts = text.split(':')
    if len(parts) == 2:
        part1 = parts[0].replace(" ", "")  ###### numbering 1,2,...
        part1 = part1.strip()
        part2 = parts[1].strip()
        return [part1[2], int(part1[3]), part2] ###### numbering
    return [None, None, None]

def make_standard_rubric():

    
    #parsing -> point_type, point, requirements
    if user_input["use_rubric"]:
        data_column = cursor.table("Rubric_PDF").select("data").df()["rubric_pdf.data"]
    # else:
        # data_column = 
    
    # print(data_column)
    new_data_column = data_column.apply(split_string).apply(pd.Series)
    new_data_column.columns = ['point_type', 'point', 'requirement']
    # print(new_data_column)
    new_data_column.to_csv(NEW_RUBRIC_PATH)
    cursor.query("DROP TABLE IF EXISTS Grade_standard;").df()
    cursor.query(
        '''CREATE TABLE IF NOT EXISTS Grade_standard (point_type TEXT(1), point INTEGER, requirement TEXT(300));'''
    ).df()
    cursor.load(NEW_RUBRIC_PATH, "Grade_standard", "csv").execute()
    print(cursor.query("SELECT * FROM Grade_standard").df())

    return


    # cursor.query("DROP TABLE IF EXISTS Rubric").df()
    # cursor.query('''CREATE TABLE IF NOT EXISTS rubric (
    #     points INTEGER,
    #     requirement TEXT(300),
    #     keyword TEXT(50),
    #     score_type BOOLEAN
    # );''')

    # print(cursor.query("SELECT * FROM rubric").df())

    
    # for index, row in data_column.iterrows():
    #     print(index, row.to_string()[21:])

    #     # requirement_no = index + 1
    #     points = int(row.to_string()[23])
    #     requirement = row.to_string()[33:]
    #     # print(type(requirement))
    #     keyword = None
    #     score_type = row.to_string()[19] in ['+']

    #     cursor.query('''INSERT INTO rubric (points, requirement, score_type) VALUES
    #                     ({points},
    #                     "{requirement}",
    #                     "{score_type}");
    #                 '''.format(points = points,
    #                            requirement = requirement,
    #                            score_type = score_type)).df()
    
    # print(cursor.query("SELECT * FROM rubric").df())




'''
1. get input
-> Problem
-> Student's Answer
-> Rubric
    - from llm by using Problem -> db
    - from pdf -> db
-> parsing and store them into rubric db

2. get score 
-> ask llm to grade based on the each rubric section, and 
    make db for storing score for each rubric section like 
    1. | 3/6 | reasons...
    2. | 6/6 | reasons...
    ...
-> merciful, moderate, tough
    get the score from those three scores and get average

-> get report for explaining the reasons why it has this grade
    -> hugface?

-> out
'''

if __name__ == "__main__":
    # cleanup()
    # try_to_import_llm()
    cursor = evadb.connect().cursor()
    user_input = handle_user_input()

    # get OpenAI key
    model = llm.get_model("gpt-3.5-turbo")
    try:
        model.key = os.environ['OPENAI_KEY']
    except KeyError:
        model.key = str(input("Enter your OpenAI key :: "))
        os.environ["OPENAI_KEY"] = model.key

    print(user_input)
    if user_input['use_rubric']:
        get_rubric_pdf()
    else:
        generate_rubric()
    




