from ..default import *
from tqdm import tqdm
from ..statistics import stats_methods

# todo: group single or not, 2*2 or not
# def check_availability(data,single_value_level=[],complex_value_level=[]):
#     for l in single_value_level:
#         if l == 'time_group':
#             values = list(data.columns.get_level_values(l).unique())
#         else:
#             values = list(data.index.get_level_values(l).unique())
#         if len(values)>1:
#             raise Exception(f'level "{l}" should have only one value, but {values} in there.')
#     for l in complex_value_level:
#         if l == 'time_group':
#             values = list(data.columns.get_level_values(l).unique())
#         else:
#             values = list(data.index.get_level_values(l).unique())
#         if len(values)==1:
#             raise Exception(f'level "{l}" should have more than one value, but {values} in there.')

def check_availability(data, level, unique_value_count):
    if level == 'time_group':
        values = list(data.columns.get_level_values(level).unique())
    else:
        values = list(data.index.get_level_values(level).unique())
    if len(values)!=unique_value_count:
        raise Exception(f'level "{level}"\'s unique_value_count should be {unique_value_count} , but {values} in there.')

def shuffle_on_level(df, level, within_subject=True, inplace=True):
    raw = list(zip(df.index.get_level_values('subject'),df.index.labels[df.index.names.index(level)],df.index.get_level_values('trial')))
    if within_subject:
        unique = list(set(raw)) # unique ind
        unique.sort(key=lambda x:x[0]) #需要先排序，然后才能groupby
        g = itertools.groupby(unique,lambda x:x[0])
        mapping = dict()
        for key,ind in g:
            ind = list(ind)
            new_ind = list(zip([i[0] for i in ind],np.random.permutation([i[1] for i in ind]),[i[2] for i in ind]))
            mapping.update(dict(zip(ind,new_ind)))
        group_labels = [mapping[i][1] for i in raw]
        # within_labels = df.index.get_level_values(within)
        # group_labels = df.index.get_level_values(level)
        # label_groups = dict()
        # for idx,(within_key,group_key) in enumerate(zip(within_labels, group_labels)):
        #     if within_key not in label_groups:
        #         label_groups[within_key] = [[],[]]
        #     label_groups[within_key][0].append(ind)
        #     label_groups[within_key][0].append(group_key)

        # group_labels = []
        # for within_key,(inds,group_keys) in label_groups.items():
        #     random.shuffle(group_keys)
        #     group_labels.extend(list(zip(inds,group_keys)))
        # group_labels.sort(key=lambda x:x[0])
        # group_labels = [i[1] for i in group_labels]
    else:
        ind = list(set(raw)) # unique ind
        new_ind = list(zip([i[0] for i in ind],np.random.permutation([i[1] for i in ind]),[i[2] for i in ind]))
        mapping = dict(zip(ind,new_ind))
        group_labels = [mapping[i][1] for i in raw]

    if inplace:
        # print(level,'\n',group_labels)
        df.index = df.index.set_labels(group_labels,level=level)
    else:
        df_new = df.copy()
        df_new.index = df.index.set_labels(group_labels,level=level)
        return df

def add_index(df, name, value):
    df[name] = value
    df.set_index(name, append=True, inplace=True)

def recover_index(df, old_df, name):
    if '_group' in name:
        values = old_df.index.get_level_values(name).map(lambda x: '0 '+' '.join(x.split(' ')[1:])).unique()
    else:
        values = old_df.index.get_level_values(name).unique()
    if len(values)==1: # make sure if the value in old_df index is unique'
        value = values[0]
    else:
        value = ','.join(values)
        # raise Exception(f'The values in level {name} should be unique')
    add_index(df, name, value)

def average(df, keep=None, remove=None):
    if keep==None:
        if remove==None:
            raise Exception('You should provide the value to "keep" or "remove"')
        else:
            all_levels = df.index.names
            keep = list(set(all_levels)-set(remove))
    return df.mean(level=keep)

'sampling'
def point_sampling(df, step_size):
    if step_size[-2:] in ['ms','Ms','MS'] and step_size[:-2].isdigit():
        step_size = step_size[:-2]+'N'
    else:
        raise Exception('step_size should be a string formatted as "10ms" or "2ms"')

    new_df = []
    for idx,group_data in df.groupby(axis=1,level='time_group'):
        old_tps = [pd.Timedelta(tp) for tp in group_data.columns.levels[1]]
        tp_indexs = [old_tps.index(tp) for tp in pd.timedelta_range(old_tps[0], old_tps[-1], freq=step_size) if tp in old_tps]
        group_data = group_data.iloc[:,tp_indexs]
        new_df.append(group_data)
    new_df = pd.concat(new_df,axis=1)

    return new_df

def window_sampling(df, win_size, sample='mean'):
    if win_size[-2:] in ['ms','Ms','MS'] and win_size[:-2].isdigit():
        win_size = win_size[:-2]+'N'
    else:
        raise Exception('win_size should be a string formatted as "20ms" or "5ms"')

    new_df = []
    for idx,group_data in df.groupby(axis=1,level='time_group'):
        group_data.columns.set_levels([pd.Timedelta(tp) for tp in group_data.columns.levels[1]], level=1, inplace=True)
        group_data_new = group_data.resample(win_size, axis=1, how='mean', level=1)
        group_data_new.columns = group_data_new.columns + pd.Timedelta(win_size[:-1]+'ns')/2 # loffset of `resample` doesn't work, so I add this line 
        if group_data_new.columns[-1]>group_data[0].columns[-1]:
            del group_data_new[group_data_new.columns[-1]]
        group_data_new.columns = pd.MultiIndex.from_product([[idx], group_data_new.columns.values.tolist()],names=['time_group','time'])
        new_df.append(group_data_new)

    new_df = pd.concat(new_df,axis=1)

    return new_df

def sampling(data,step_size='1ms',win_size='1ms',sample='mean'):
    if step_size!='1ms':
        data = point_sampling(data, step_size)
    elif win_size!='1ms':
        data = window_sampling(data, win_size, sample=sample)
    return data

'map and apply'
# def roll_on_levels(df, func, arguments_dict=dict(), levels='time', prograssbar=True):
#     col_level = df.columns.names[1]
#     df = df.stack(col_level)
#     result = []
#     group_ids = []

#     for group_id,group_data in tqdm(df.groupby(level=levels), ncols=0, disable=(not prograssbar)):
#         # print(group_data)
#         result_one_group = func(group_data, **arguments_dict)

#         group_ids.append(group_id)
#         result.append(result_one_group)

#     if type(levels)==str or len(levels)==1:
#         index = pd.Index(group_ids, name=levels)
#     else:
#         index = pd.MultiIndex.from_tuples(group_ids, names=levels)

#     result = pd.DataFrame(result, index=index)
#     # result.name = df.name
#     recover_index(result, df, 'condition_group')
#     return result.unstack(col_level)

from concurrent.futures import ProcessPoolExecutor
def roll_on_levels(df, func, arguments_dict=dict(), levels='time', prograssbar=True, parallel=False):
    col_level = df.columns.names[1]
    df = df.stack(col_level)
    data_results = []
    annotation_results = []
    group_ids = []

    if parallel is False:
        for group_id,group_data in tqdm(df.groupby(level=levels), ncols=0, disable=(not prograssbar)):
            result_one_group = func(group_data, **arguments_dict)

            group_ids.append(group_id)
            if type(result_one_group) is tuple:
                if len(result_one_group)==2:
                    data_results.append(result_one_group[0])
                    annotation_results.append(result_one_group[1])
                else:
                    raise Exception('The return value of func should not above 2!')
            else:
                data_results.append(result_one_group)
    else:
        if parallel is True: parallel = None # if max_workers is None or not given, it will default to the number of processors on the machine
        with ProcessPoolExecutor(max_workers=parallel) as executor:
            tasks = [(group_id, 
                      executor.submit(func, group_data, **arguments_dict))
                    for group_id,group_data in df.groupby(level=levels)]
            with tqdm(total=len(tasks), disable=(not prograssbar)) as pbar:  
                while 1:
                    count_doned = sum([task.done() for group_id,task in tasks])
                    pbar.update(count_doned - pbar.n)
                    if count_doned==len(tasks):
                        break

        for group_id,task in tasks:
            group_ids.append(group_id)
            result_one_group = task.result()
            if type(result_one_group) is tuple:
                if len(result_one_group)==2:
                    data_results.append(result_one_group[0])
                    annotation_results.append(result_one_group[1])
                else:
                    raise Exception('The return value of func should not above 2!')
            else:
                data_results.append(result_one_group)

    if type(levels)==str or len(levels)==1:
        index = pd.Index(group_ids, name=levels)
    else:
        index = pd.MultiIndex.from_tuples(group_ids, names=levels)
    
    data_results = pd.DataFrame(data_results, index=index)
    recover_index(data_results, df, 'condition_group')

    if len(annotation_results)==0:
        return data_results.unstack(col_level)
    else:
        annotation_results = pd.DataFrame(annotation_results, index=index)
        recover_index(annotation_results, df, 'condition_group')
        return data_results.unstack(col_level), annotation_results.unstack(col_level)

# ugly code. To do.
def roll_on_levels_and_compare(df, func, arguments_dict=dict(), levels='time', between='condition_group', in_group='subject',prograssbar=True):
    col_level = df.columns.names[1]
    df = df.stack(col_level)
    result = []
    group_ids = []

    for group_id,group_data in tqdm(df.groupby(level=levels), ncols=0, disable=(not prograssbar)):
        data_sub = [group_data.mean(level=in_group).mean(axis=1) 
            for group_id,group_data in group_data.groupby(level=between)]
        
        # ipdb.set_trace()
        result_one_group = func(data_sub, **arguments_dict)['pvalue']
        # re_add_name = group_data.index.get_level_values(between)[0][2:]
        
        group_ids.append(group_id)
        result.append(result_one_group)

    if type(levels)==str or len(levels)==1:
        index = pd.Index(group_ids, name=levels)
    else:
        index = pd.MultiIndex.from_tuples(group_ids, names=levels)

    result = pd.DataFrame(result, index=index)
    
    recover_index(result, group_data, between)

    return result.unstack(col_level)

def stats_compare(df, comparison, levels='time', between='condition_group', in_group='subject'):
    condition_groups = df.index.get_level_values(between).unique()
    if comparison['sig_limit']>0 and len(condition_groups)==2:
        if comparison['win']!='1ms':
            df = window_sampling(df, comparison['win'], comparison['method'])
        stats_result = roll_on_levels_and_compare(df, comparison['test'], levels=levels, between=between, in_group=in_group)
        pval_result = stats_result
        return pval_result
    else:
        return None
