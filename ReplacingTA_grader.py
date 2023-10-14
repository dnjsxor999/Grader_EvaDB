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
RUBRIC_NO = 0


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
        << You will need the 'Problem' and 'Answer' you want to score >>\n"
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

    answer_str = answer_str.replace("\"", "")


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
    # print(user_input)
    cursor.query("DROP TABLE IF EXISTS Rubric_PDF;").df()
    cursor.query("LOAD PDF '{}' INTO Rubric_PDF;".format(user_input['rubric_pdf_name'])).df()
    # print(cursor.query("SELECT * FROM Rubric_PDF").df())
    print("✅ Rubric successfully generated!")
    return

def generate_rubric():
    # llm 이용 promt(..., system="~") -> get rubric -> store them into table
    # -> JSON format
    global RUBRIC_NO

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
                    [no prose]
                    [Output only JSON]
                    Give me {rubrics_no} grading rubrics for total {total_score} points for below question:
                    "{question}"
                    Do not include any explanations, only provide compliant JSON response following this format without deviation:
                    [{{
                        point_type: "+",
                        points: value of point,
                        requirement: in one string sentence
                    }}]
                    '''.format(rubrics_no = rubric_no_request,
                               total_score = total_score_request,
                               question = user_input["question"])
    print(PROMPT_RUBRIC)
    response = model.prompt(PROMPT_RUBRIC,
                            system="Answer like you are Teaching Assistant", temperature=0.5)
    
    print(response)

    # json parsing
    try:
        df_json = pd.read_json(str(response))
        RUBRIC_NO = df_json.shape[0]
        df_json['rubric_no'] = df_json.index + 1
        df_json.to_csv(NEW_RUBRIC_PATH, index=False)
        print("✅ Rubric successfully generated!")
    except ValueError:
        print("wrong format of JSON from llm, run again")
    except Exception as e:
        print(f"An error occurred: {e}")



def split_string(text):
    parts = text.split(':') # must be formatted by "part1 : part2"
    if len(parts) == 2:
        part1 = parts[0].replace(" ", "")  ###### numbering 1,2,...
        part1 = part1.strip()
        part2 = parts[1].strip()
        return [part1[2], int(part1[3]), part2] ###### numbering
    return [None, None, None]

def make_standard_rubric():
    global RUBRIC_NO
    
    #parsing -> point_type, point, requirements
    if user_input["use_rubric"]:
        data_column = cursor.table("Rubric_PDF").select("data").df()["rubric_pdf.data"]
        # print(data_column)
        new_data_column = data_column.apply(split_string).apply(pd.Series)
        new_data_column.columns = ['point_type', 'points', 'requirement']
        # print(new_data_column)
        RUBRIC_NO = new_data_column.shape[0]
        new_data_column['rubric_no'] = new_data_column.index + 1
        new_data_column.to_csv(NEW_RUBRIC_PATH)

    cursor.query("DROP TABLE IF EXISTS Grade_standard;").df()
    cursor.query(
        '''CREATE TABLE IF NOT EXISTS Grade_standard (point_type TEXT(1), points INTEGER, requirement TEXT(300), rubric_no INTEGER);'''
    ).df()
    cursor.load(NEW_RUBRIC_PATH, "Grade_standard", "csv").execute()
    print(cursor.query("SELECT * FROM Grade_standard").df())
    print("✅ Standard Rubric table successfully stored!")
    return

def grading():

    # create Grade_Result table for collecting various version of result
    llm_system = [("tough", "0.2"), ("moderate", "0.5"), ("merciful", "0.7")] # grader_style, and temperature value

    cursor.query("DROP TABLE IF EXISTS Grade_Result;").df()
    cursor.query(
        '''CREATE TABLE IF NOT EXISTS Grade_Result (rubric_no INTEGER, points INTEGER);'''
    ).df()

    # print(cursor.query("SHOW FUNCTIONS;").df())

    # create LLM function
    # cursor.query("CREATE FUNCTION IF NOT EXISTS LLMFunction IMPL 'evadb_data/functions/LLMFunction.py'").df()

    # PROMPT_GRADING = '''Based on the given criteria and bound points, score/grade this student's answer {student_answer}
    #                     Do not include any explanations, only provide points that student will get.
    #                 '''.format(student_answer=user_input['answer'])
    # for i in range(len(llm_system)):
    #     cursor.table("Grade_standard").select("LLMFunction({queries}, requirement, {systems}, {temperatures}, points)".format(
    #         queries=PROMPT_GRADING,
    #         systems=llm_system[i][0],
    #         temperatures=llm_system[i][1]
    #     )).df()

    def try_llm_prompt(command, system, temperature):
        return str(model.prompt(command, system=command, temperature=temperature))
    
    PROMPT_GRADING = '''
                        [no prose]
                        Here is the criteria: {criteria},
                        Total score for this criteria {total_points},
                        Based on the given criteria  score/grade this student's answer: {student_answer}
                        Don't include any explanations in your responses, only provide just one single integer that student will get (i.e '3'), and not greater than total score.
                    '''
    PROMPT_SYSTEM = "You are Teaching Assistant and {} grader."

    requirements = cursor.query("SELECT points, requirement FROM Grade_standard").df()
    print(requirements)
    for i in range(RUBRIC_NO):
        current_criteria = requirements["grade_standard.requirement"][i]
        current_total_points = requirements["grade_standard.points"][i]
        print(current_criteria, current_total_points)
        for j in range(len(llm_system)):
            if current_total_points == 0:
                continue
            PROMPT_GRADING = PROMPT_GRADING.format(criteria=current_criteria, total_points=current_total_points, student_answer=user_input['answer'])
            PROMPT_SYSTEM = PROMPT_SYSTEM.format(llm_system[j][0])
            get_scored = try_llm_prompt(PROMPT_GRADING, PROMPT_SYSTEM, float(llm_system[j][1]))
            print(get_scored, type(str(get_scored)))
            try:
                get_scored = int(get_scored)
            except ValueError:
                print("couldn't get score from llm, let me try again")
                trial = 3
                while trial != 0:
                    if len(try_llm_prompt(PROMPT_GRADING, PROMPT_SYSTEM, float(llm_system[j][1]))) == 1:
                        get_scored = int(get_scored)
                        break
                    trial -= 1
                print("couldn't get score from llm, run again")
            except Exception as e:
                print(f"An error occurred: {e}")
            
            if get_scored > current_total_points:
                get_scored = current_total_points

            cursor.query(f"INSERT INTO Grade_Result (rubric_no, points) VALUES ({i+1}, {get_scored});").execute()

    
    print(cursor.query("SELECT * FROM Grade_Result;").df())
    # print(cursor.query("SELECT grade_result.rubric_no, AVG(grade_result.points) FROM Grade_result GROUP BY grade_result.rubric_no").df())
    mean_of_scores = cursor.query("SELECT * FROM Grade_Result;").df().groupby('grade_result.rubric_no').mean()
    print(mean_of_scores)
    total_score = mean_of_scores["grade_result.points"].sum()
    print(total_score)
    return total_score







'''
1. get input
-> Problem
-> Student's Answer
-> Rubric
    - from llm by using Problem -> db
    - from pdf -> db
-> parsing and store them into "Grade_standard" db

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
    # test()
    if user_input['use_rubric']:
        get_rubric_pdf()
    else:
        generate_rubric()
    
    make_standard_rubric()

    # 2.

    print("✅The total score is :: ", grading())




