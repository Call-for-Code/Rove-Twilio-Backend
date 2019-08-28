from priority_mapping import *
with open("priority_levels.txt","r") as f:
    lines=f.readlines()
with open("priority_dict.csv","w") as f:
    for line in lines:
        first_elem=line.split("-")[0]
        if not str.isdigit(first_elem):
            continue
        # print(first_elem)
        space_split=line.split(" ")
        priority=space_split[0].split("-")[1]
        key_word=" ".join(space_split[1:]).strip()
        print(priority,key_word)
        final="{},{}\n".format(key_word,priority_mapping[priority])
        f.write(final)
        