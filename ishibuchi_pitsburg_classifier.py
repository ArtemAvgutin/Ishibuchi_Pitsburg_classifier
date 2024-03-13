# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split

df = pd.read_csv('Data.csv').drop('Id', axis=1)

df.head(5)

# класс для построения правил ишибучи и расчетов достоверности

class Ishibuchi:
# класс выполняет обучение и предсказание на основе набора правил и данных.


    def __init__(self, rules, class_len):
        self.rule_base = rules
        self.class_len = class_len

# метод выполняет обучение модели по переданным тренировочным данным, а также описаниям терминов
    def fit(self, X_train, y_train, *terms):
        self.terms = list(terms)

        self.variable_terms = self.terms_definition(X_train)

        self.rule_class_cf_assign(X_train, y_train, self.rule_base)

        return self

# метод определяет диапазоны значений для каждого термина на основе квантилей данных тренировочного набора.
    def terms_definition(self, train_set):
        terms = self.terms
        terms_dict = {}
        quantiles = np.arange(0., 1., 1 / len(terms))[1:]

        for var in train_set.columns:
            terms_dict[var] = {k:None for k in terms}
            terms_quants = np.quantile(np.array(train_set[var]), quantiles)
            for term, quant in zip(terms, terms_quants):
                terms_dict[var][term] = quant

        return terms_dict


# определяет функции принадлежности для каждого термина.
    def membership_function(self, term):

        def too_small(x, quant, right_border):
            if x >= right_border:
                return 0
            elif x <= quant:
                return 1
            else:
                return (right_border - x) / (right_border - quant)

        def too_big(x, quant, left_border):
            if x <= left_border:
                return 0
            if x >= quant:
                return 1
            else:
                return (x - left_border) / (quant - left_border)

        def dc_term():
            return 1

        def other_terms(x, quant, left_border, right_border):
            if (x <= left_border) | (x >= right_border):
                return 0
            elif left_border < x <= quant:
                return (x - left_border) / (quant - left_border)
            elif quant < x < right_border:
                return (right_border - x) / (right_border - quant)

        if term == self.terms[0]:
            return too_small
        elif term == self.terms[-2]:
            return too_big
        elif term == self.terms[-1]:
            return dc_term
        else:
            return other_terms


# метод вычисляет значение принадлежности для каждого правила исходя из переданных значений
    def count_membership_over_the_rule(self, rule:list, X):
        membership_values = []
        for t, v in zip(rule, X.keys()):
            member_func = self.membership_function(t)
            quant_index = self.terms.index(t)
            values = list(self.variable_terms[v].values())
            quant = values[quant_index]
            if 0 < quant_index < len(self.terms) - 2:
                left_border = values[quant_index - 1]
                right_border = values[quant_index + 1]

                membership_values.append(member_func(X[v], quant, left_border, right_border))
            elif quant_index == 0:
                right_border = values[quant_index + 1]

                membership_values.append(member_func(X[v], quant, right_border))

            elif quant_index == len(self.terms) - 2:
                left_border = values[quant_index - 1]

                membership_values.append(member_func(X[v], quant, left_border))

            else:
                membership_values.append(member_func())
        members_wo_zeros = [x for x in membership_values if x != 0]
        return min(members_wo_zeros) if len(members_wo_zeros) > 0 else 0



# метод вычисляет суммарное значение принадлежности для каждого класса на основе правила и тренировочного набора.
    def class_membership(self, X_train, y_train, class_, rule):
        class_set = X_train.iloc[y_train[y_train == class_], :]
        membership_sum = 0

        for i in range(class_set.shape[0]):
            membership_sum += self.count_membership_over_the_rule(rule, class_set.iloc[i,:])

        return membership_sum / class_set.shape[0]


# метод вычисляет значимость класса с помощью коэффициента достоверности для каждого класса.
    def cf_counter(self, class_betas_dict, true_class):
        true_class_beta = class_betas_dict[true_class]
        others_betas_mean = sum([class_betas_dict[x] for x in class_betas_dict.keys() if x != true_class]) / (self.class_len - 1)
        return (true_class_beta - others_betas_mean) / sum([class_betas_dict[x] for x in class_betas_dict.keys()])


# метод присваивает каждому правилу класс и коэффициент достоверности на основе тренировочного набора.
    def rule_class_cf_assign(self, X_train, y_train, rule_base):
        class_rule_assign = {}

        for rule in rule_base:
            betas = {class_:None for class_ in y_train.unique()}
            rule_s = ' '.join(rule)
            class_rule_assign[rule_s] = {}
            for class_ in betas.keys():
                betas[class_] = self.class_membership(X_train, y_train, class_, rule)

            class_rule_assign[rule_s]['class'] = list(betas.keys())[np.argmax(list(betas.values()))]
            class_rule_assign[rule_s]['cf'] = self.cf_counter(betas, class_rule_assign[rule_s]['class'])

        self.class_rule_assignment = class_rule_assign


# метод предсказывает класс для новых данных X на основе правил и коэффициентов достоверности.
    def predict(self, X):
        best_class = None
        best_metric = -1
        for rule in self.class_rule_assignment.keys():
            div_rule = rule.split()
            metric = self.count_membership_over_the_rule(div_rule, X) * self.class_rule_assignment[rule]['cf']
            if metric > best_metric:
                best_metric = metric
                best_class = self.class_rule_assignment[rule]['class']

        return best_class

class Pittsburg:

    def __init__(self, X, y, *terms, initial_population=250, individual_length=10, mutation_probability=0.01, generation_length=100):
        self.generation_length=generation_length
        self.individual_length = individual_length
        self.initial_population = initial_population
        self.mutation_prob = mutation_probability
        self.X = X
        self.y = y
        self.terms = terms
        self.class_number = len(y.unique())

        self.population = [[np.random.choice(self.terms, self.X.shape[1])
                            for _ in range(individual_length)]
                            for _ in range(initial_population)]

# метод создает объекты ишибучи для каждого правила в популяции.
    def build_ishis(self):
        individs_dict = {}
        for i, ind in enumerate(self.population):
            individs_dict[i] = {'rules':ind,
                                'ishi':Ishibuchi(ind, self.class_number).fit(self.X, self.y, *self.terms)}

        self.individuals_dict = individs_dict

# метод вычисляет число правильно классифицированных элементов для данного правила.
    def NCP(self, individual):
        ncp = 0
        predictions = []
        for i in range(self.X.shape[0]):
            predictions.append(individual.predict(self.X.iloc[i, :]))
        number_of_correct = 0
        for p_class, t_class in zip(predictions, self.y):
            if p_class == t_class:
                number_of_correct += 1
        return number_of_correct
# метод вычисляет NCP для каждого правила в популяции и присваивает их соответствующим индивидуумам.
    def assign_ncp_to_individuals(self):
        for individ_key in self.individuals_dict.keys():
            self.individuals_dict[individ_key]['NCP'] = self.NCP(self.individuals_dict[individ_key]['ishi'])
# метод возвращает список значений NCP из индивидуумов.
    def take_ncps(self):
        ncps = []
        for individ_key in self.individuals_dict.keys():
            ncps.append(self.individuals_dict[individ_key]['NCP'])
        return ncps
# метод вычисляет вероятности выбора каждого индивидуума в качестве родителя.
    def assign_parent_probabilities(self):
        ncps = self.take_ncps()
        min_ncp = min(ncps)
        sum_ncp = sum(ncps)
        division = (sum_ncp - len(ncps)*min_ncp)
        for individ_key in self.individuals_dict.keys():
            self.individuals_dict[individ_key]['Parent_Probability'] = (self.individuals_dict[individ_key]['NCP'] - min_ncp) / (1 if division == 0 else division)
        return division

# метод выбирает индекс второго родителя из оставшихся индивидуумов.
    def choose_second_parent(self, first_parent_ind, parents_indecies):
        parents_indecies = list(parents_indecies.copy())
        parents_indecies.remove(first_parent_ind)

        second_parent = None
        while second_parent is None:
            parent_prob = np.random.uniform()
            for parent_ind in parents_indecies:
                if self.individuals_dict[parent_ind]['Parent_Probability'] >= parent_prob:
                    second_parent = parent_ind
                    break
        return second_parent

# метод выполняет операцию скрещивания двух родителей, создавая новое правило.
    def crossover(self, parent_one, parent_two):
        child_one = parent_one.copy()
        child_two = parent_two.copy()
        child = [child_one[j] if np.random.uniform() < 0.5 else child_two[j] for j in range(len(child_one))]
        return child

# метод применяет операцию скрещивания к популяции индивидуумов.
    def apply_uniform_crossover(self):
        new_population = []
        parents_indecies = list(self.individuals_dict.keys())
        for parent_ind in parents_indecies:
            parent_one = self.individuals_dict[parent_ind]['rules']
            parent_two = self.individuals_dict[self.choose_second_parent(parent_ind, parents_indecies)]['rules']

            child = self.crossover(parent_one, parent_two)

            new_population.append(child)

        return new_population

# метод мутации к новой популяции.
    def apply_mutation(self, new_population):
        for i in range(len(new_population)):
            for j in range(len(new_population[i])):
                mut = np.random.uniform()
                if mut <= self.mutation_prob:
                    new_population[i][j] = np.random.choice(self.terms, self.X.shape[1])

# метод создает новую популяцию путем применения скрещивания и мутации, а также сохраняет лучший индивидуум из предыдущего поколения.
    def new_generation(self):
        new_population = self.apply_uniform_crossover()
        self.apply_mutation(new_population)
        elite_index = np.argmax([x['NCP'] for x in self.individuals_dict.values()])
        random_from_new_population = np.random.randint(len(new_population))

        new_population[random_from_new_population] = self.individuals_dict[elite_index]['rules']

        del self.population
        del self.individuals_dict

        self.population = new_population

# метод выполняет генерацию новых поколений популяции и возвращает лучший индивидуум.
    def make_generations(self):
        print('Начало процесса')
        for i in range(1, self.generation_length + 1):
            print(f'/////////////////Generation {i - 1} start/////////////////////')
            print('Building population')
            self.build_ishis()
            print('Assigning ncps')
            self.assign_ncp_to_individuals()
            if i == self.generation_length:
                break
            print('Assigning initial probabilities')
            division = self.assign_parent_probabilities()
            print(f'Generation {i}. MAX NCP is : {np.max([x["NCP"] for x in self.individuals_dict.values()])}')
            if division == 0:
                print('All the individuals are same')
                break
            self.new_generation()
        return self.individuals_dict[np.argmax([x['NCP'] for x in self.individuals_dict.values()])]['ishi']

X_train, X_test, y_train, y_test = train_test_split(df.drop('quality', axis=1), df['quality'],
                                                    test_size=0.2, stratify=df['quality'])

ishibuchi = Pittsburg(X_train, y_train, 'TS', 'S', 'M', 'B', 'TB', 'DC',
                      initial_population=20,
                      individual_length=50,
                      generation_length=20) #Возьму 20 для быстроты работы

best_individ = ishibuchi.make_generations()

predictions = []
for i in range(X_test.shape[0]):
    predictions.append(best_individ.predict(X_test.iloc[i, :]))

true_answers = 0
for pr, test in zip(predictions, y_test):
    if pr == test:
        true_answers += 1

print(f'Точность работы алгоритма: {round(true_answers * 100/y_test.shape[0])} %')
