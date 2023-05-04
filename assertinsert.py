### Grabs string for runActivity() call and uses it as assert error message.

import os
import re
import sys

# Define the input and output file paths
if len(sys.argv) < 2:
    print("specify the file to attack")
    sys.exit(-1)

output_file_path = sys.argv[1]


if not os.path.exists(output_file_path):
    print(output_file_path, "Does not exist")
    sys.exit(-1)

input_file_path = output_file_path + ".bak"

os.rename(output_file_path, input_file_path)

# Define pattern to search for runActivity calls with XCTAssert assertions
run_activity_pattern = r'runActivity\("Then verify ([^"]+)"'
xct_assert_pattern = r'(^.*XCTAssert.*\(.+)\)'

# Open the input and output files
with open(input_file_path, 'r') as input_file, \
    open(output_file_path, 'w') as output_file:

    info_message = " "
    # Iterate over each line in the input file
    for line in input_file:

        # Search for runActivity calls and XCTAssert assertions
        run_activity_match = re.search(run_activity_pattern, line)
        xct_assert_match = re.search(xct_assert_pattern, line)

        if run_activity_match:
            # Retrieve the original runActivity string argument
            run_activity_arg = run_activity_match.group(1)
            #print("runact match", run_activity_arg)
            info_message = run_activity_arg
            output_file.write(line)

        elif xct_assert_match:
            print("runact match", info_message)
            # Retrieve the assertion
            assert_str = xct_assert_match.group()
            # print("assert match", assert_str)

            # shouldn't have kept the info_message ), but it does
            if assert_str[-1] == ')':
                assert_str = assert_str[:-1]

            # fix up some of the language
            if re.search(r'exists', info_message):
                info_message = re.sub("exists", "does not exist", info_message)
            elif re.search(r'matches', info_message):
                info_message = re.sub("matches", "does not match", info_message)
            elif re.search(r' is no ', info_message):
                info_message = re.sub(" is ", " should not be any ", info_message)
            elif re.search(r' is ', info_message):
                info_message = re.sub(" is ", " is not ", info_message)
            elif re.search(r' are no ', info_message):
                info_message = re.sub(" are no ", " should not be ", info_message)
            elif re.search(r' are ', info_message):
                info_message = re.sub(" are ", " are not ", info_message)

            # Replace the original assertion with the modified one in the line
            modified_line = assert_str + ', "' + info_message.capitalize() + '")\n'
            # print(modified_line)
            # Write the modified line to the output file
            output_file.write(modified_line)

        else:
            # If the line does not contain a matching pattern, write it to the output file unchanged
            output_file.write(line)


print(f"Finished processing '{input_file_path}' and wrote the output to '{output_file_path}'.")
