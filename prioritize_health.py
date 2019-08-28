import nltk
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')
import gensim
from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_watson.natural_language_understanding_v1 import Features, KeywordsOptions

def is_useless(word):   
    pos=nltk.pos_tag([word])[0][1]
    if pos in ["DT","IN","WRB","RB"]:
        return True
    return False

def prioritize_health(sentence,model):
    priority_dict={}
    with open("priority_dict.csv","r") as f:
        for line in f:
            # print(line.strip().split(","))
            comma_split=line.strip().split(",")
            symptom=",".join(comma_split[:-1])
            priority=int(comma_split[-1])
            print(symptom,priority)
            priority_dict[symptom]=priority
    symptoms=priority_dict.keys()
    natural_language_understanding = NaturalLanguageUnderstandingV1(
        version='2019-07-12',
        iam_apikey='eFxfKzryOzn_gY9b_s_ZX1pxN1T1dsXSjVsH6QC65KzO',
        url='https://gateway.watsonplatform.net/natural-language-understanding/api'
    )
    result=natural_language_understanding.analyze(
        text=sentence,
        features=Features(keywords=KeywordsOptions())).get_result()
    print(result)
    keywords=[x['text'] for x in result['keywords']]
    print(keywords)
    #find key words in the sentence. for each word, find nearest keywords based on the avg cosine score
    print(symptoms[:10])
    closest_symptoms=[] #add one for each keyword
    for cur_keyword in keywords:
        best_avg_sim=0
        best_symptom=None
        print("Finding closest match for keyword={}".format(cur_keyword))
        test_keyword=cur_keyword.split(" ")[-1]
        print("Test keyword={}".format(test_keyword))
        for cur_symptom in symptoms:
            symptom_tokens=[x.lower() for x in nltk.word_tokenize(cur_symptom) if not is_useless(x) and x.isalpha()]
            total_sim=0
            total_cnt=0
            # print("Symptom={}".format(cur_symptom))
            # print("Symptom tokens={}".format(symptom_tokens))
            for token in symptom_tokens:
                # print("Token={}".format(token))
                if token not in model.vocab or token==test_keyword:
                    # print("Token not found in vocab, skipping")
                    continue
                #compute similarity of keyword and otken
                cur_sim=model.similarity(test_keyword,token)
                # print("cur_sim={}".format(cur_sim))
                if cur_sim<-0.2 or cur_sim>0.2:
                    total_sim+=cur_sim
                    total_cnt+=1
            if total_cnt:
                avg_sim=float(total_sim)/total_cnt
                print("total_sim={},total_cnt={},avg_sim={}".format(total_sim,total_cnt,avg_sim))
                if avg_sim>best_avg_sim:
                    best_avg_sim=avg_sim
                    best_symptom=cur_symptom
        print(best_avg_sim,best_symptom)
    priority_score=priority_dict[best_symptom]
    res=(keywords,priority_score)
    print("Result={}".format(res))
    return res

def main():
    sentence="i have a small wound and broken leg"
    model = gensim.models.KeyedVectors.load_word2vec_format('GoogleNews-vectors-negative300-SLIM.bin', binary=True)
    # print("hello" in model.vocab)
    result=prioritize_health(sentence,model)
    # print(result)
    

if __name__ == '__main__':
    main()
    