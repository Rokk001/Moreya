/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef SAFESAVE_H
#define SAFESAVE_H

#include <boost/filesystem.hpp>

#include <exception>
#include <functional>
#include <string>

//! \brief Saves a file so that a failed save never destroys the file that is already there.
namespace SafeSave
{
    //! \brief Writes the whole new content into the file with the given name and returns true on success.
    typedef std::function<bool(const std::string&)> Writer;

    //! \brief Removes a file and ignores every error (the file may not exist).
    inline void removeQuietly(const boost::filesystem::path& file)
    {
        boost::system::error_code ignored;
        boost::filesystem::remove(file, ignored);
    }

    //! \brief Replaces the target file with the content the writer produces. The content is written completely
    //! into a temp file next to the target first, so a failed write leaves the old file and its .bak as they
    //! were. Only then the old file is copied to a temp backup (checked for its size) that replaces the .bak, and
    //! the temp file replaces the target in one rename. File system errors and exceptions end in a return of
    //! false and a text in error, never in an exception.
    inline bool replaceFile(const boost::filesystem::path& target, const Writer& writer, std::string& error)
    {
        error.clear();
        boost::filesystem::path tempPath;
        boost::filesystem::path backupTempPath;
        try
        {
            const std::string targetName = target.string();
            tempPath = boost::filesystem::path(targetName + ".tmp");
            const boost::filesystem::path backupPath(targetName + ".bak");
            backupTempPath = boost::filesystem::path(targetName + ".bak.tmp");
            boost::system::error_code fileError;

            // A leftover of an earlier failed save must not be taken for a new file
            removeQuietly(tempPath);
            removeQuietly(backupTempPath);

            bool written = false;
            try
            {
                written = writer(tempPath.string());
            }
            catch(const std::exception& e)
            {
                error = std::string("exception while writing: ") + e.what();
            }
            if(!written)
            {
                if(error.empty())
                    error = "the map could not be written";
                removeQuietly(tempPath);
                return false;
            }

            // A missing file is reported as an error by the error_code overloads, but it only means a new file
            const boost::filesystem::file_status targetStatus = boost::filesystem::status(target, fileError);
            const bool targetExists = boost::filesystem::exists(targetStatus);
            if(targetStatus.type() == boost::filesystem::file_not_found)
                fileError.clear();
            if(fileError)
            {
                error = "could not check the old file: " + fileError.message();
                removeQuietly(tempPath);
                return false;
            }

            if(targetExists)
            {
                // The backup is made from the complete old file and replaces the old backup only when complete
                boost::filesystem::copy_file(target, backupTempPath, fileError);
                boost::system::error_code sizeError;
                boost::system::error_code backupSizeError;
                if(!fileError)
                {
                    const boost::uintmax_t oldSize = boost::filesystem::file_size(target, sizeError);
                    const boost::uintmax_t backupSize = boost::filesystem::file_size(backupTempPath, backupSizeError);
                    if(sizeError || backupSizeError || (oldSize != backupSize))
                        fileError = boost::system::errc::make_error_code(boost::system::errc::io_error);
                }
                if(!fileError)
                    boost::filesystem::rename(backupTempPath, backupPath, fileError);
                if(fileError)
                {
                    error = "could not back up the old file: " + fileError.message();
                    removeQuietly(backupTempPath);
                    removeQuietly(tempPath);
                    return false;
                }
            }

            boost::filesystem::rename(tempPath, target, fileError);
            if(fileError)
            {
                error = "could not replace the old file: " + fileError.message();
                removeQuietly(tempPath);
                return false;
            }
            return true;
        }
        catch(const std::exception& e)
        {
            error = std::string("exception while saving: ") + e.what();
            removeQuietly(tempPath);
            removeQuietly(backupTempPath);
            return false;
        }
    }
}

#endif // SAFESAVE_H
